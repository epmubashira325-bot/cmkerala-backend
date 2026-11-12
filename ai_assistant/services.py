import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from django.conf import settings
from rest_framework.exceptions import ValidationError, APIException
from pydantic import ValidationError as PydanticValidationError

from google import genai
from google.genai import types
from google.genai.errors import APIError

from departments.models import Department
from grievances.models import Grievance
from .prompts import (
    GrievanceAIAnalysisPydantic,
    AI_TRIAGE_SYSTEM_INSTRUCTION,
    build_analysis_user_prompt,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "1.0.0"

STANDARD_CATEGORIES = [
    "Infrastructure",
    "Healthcare & Medical",
    "Revenue & Land Records",
    "Law & Order",
    "Education & Schools",
    "Water Supply & Sanitation",
    "Transport & Traffic",
    "Social Welfare & Pensions",
    "Environment & Forests",
    "Electricity & Power",
    "Local Self Government (Panchayat/Municipality)",
    "Civil Supplies & Rationing",
    "General Public Grievance"
]


class AIServiceUnavailable(APIException):
    status_code = 503
    default_detail = "AI Grievance Assistant service is temporarily unavailable."
    default_code = "ai_service_unavailable"


class GeminiAssistantService:
    """
    Resilient service layer orchestrating Google GenAI interaction for complaint
    classification, priority scoring, and executive summarization using the official
    google-genai SDK.

    Supports:
    - Primary model attempt (gemini-3.8-flash)
    - Single retry for transient errors
    - Automatic fallback to verified model (gemini-3.6-flash) on 503/504 errors
    - Preserves structured JSON output via GrievanceAIAnalysisPydantic
    - Captures requested vs actual model in ai_metadata
    """

    REQUEST_TIMEOUT_MS = 25_000  # 25 seconds

    @classmethod
    def get_client(cls) -> genai.Client:
        """
        Initializes GenAI client with GEMINI_API_KEY from settings.
        Configures an explicit HTTP client timeout to prevent indefinite hangs.
        """
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key or not str(api_key).strip():
            logger.error("GEMINI_API_KEY is not configured in backend settings.")
            raise AIServiceUnavailable("AI integration is not configured. GEMINI_API_KEY is missing.")

        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=cls.REQUEST_TIMEOUT_MS)
        )

    @classmethod
    def get_primary_model(cls) -> str:
        model = getattr(settings, 'GEMINI_MODEL', None)
        if not model or not str(model).strip():
            return "gemini-3.6-flash"
        return str(model).strip()

    @classmethod
    def get_fallback_model(cls) -> Optional[str]:
        model = getattr(settings, 'GEMINI_FALLBACK_MODEL', None)
        if not model or not str(model).strip():
            return None
        return str(model).strip()

    @classmethod
    def _execute_generation(cls, client: genai.Client, model_name: str, prompt: str) -> Any:
        """
        Executes a single generate_content request with Gemini 3.8/3.x compatible options.
        Avoids deprecated generation hyperparameters (top_k, etc.).
        """
        config = types.GenerateContentConfig(
            system_instruction=AI_TRIAGE_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=GrievanceAIAnalysisPydantic,
        )

        return client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

    @classmethod
    def analyze_grievance(
        cls,
        subject: str,
        description: str,
        district: str
    ) -> Dict[str, Any]:
        """
        Analyzes grievance with primary model, retrying once on transient errors,
        and falling back to the configured fallback model on 503/504 if primary fails.
        """
        subject = subject.strip()
        description = description.strip()
        district = district.strip()

        # Retrieve active departments from database
        active_departments = list(Department.objects.filter(is_active=True).values_list('name', flat=True))
        if not active_departments:
            active_departments = ["General Administration Department"]

        user_prompt = build_analysis_user_prompt(
            subject=subject,
            description=description,
            district=district,
            allowed_departments=active_departments,
            standard_categories=STANDARD_CATEGORIES
        )

        primary_model = cls.get_primary_model()
        fallback_model = cls.get_fallback_model()
        client = cls.get_client()

        response = None
        actual_model_used = primary_model
        fallback_used = False
        last_error = None

        # Attempt 1: Primary model
        for attempt in range(2):  # At most 1 retry for transient glitches
            try:
                logger.info("Attempt %d: Calling primary Gemini model '%s'", attempt + 1, primary_model)
                response = cls._execute_generation(client, primary_model, user_prompt)
                actual_model_used = primary_model
                break
            except APIError as api_err:
                last_error = api_err
                err_code = getattr(api_err, 'code', None)
                # Fail immediately without retry on auth/client errors
                if err_code in (400, 401, 403, 404):
                    logger.error("Non-retryable client/auth APIError from Gemini: Code %s - %s", err_code, api_err.message)
                    raise AIServiceUnavailable(f"Gemini API authentication or configuration error: {api_err.message}")
                # For 503 (high demand) or 504 (deadline exceeded), do not loop retry primary; proceed to fallback
                if err_code in (503, 504):
                    logger.warning("Primary model '%s' returned HTTP %s. Proceeding to fallback.", primary_model, err_code)
                    break
            except Exception as exc:
                last_error = exc
                err_str = str(exc)
                if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                    raise AIServiceUnavailable("Gemini API rate limit exceeded. Please try again shortly.")
                logger.warning("Primary model attempt %d encountered error: %s", attempt + 1, err_str[:120])

        # Attempt 2: Fallback model if primary failed with transient service error and fallback is configured
        if response is None and fallback_model and fallback_model != primary_model:
            try:
                logger.info("Engaging verified fallback Gemini model '%s'", fallback_model)
                response = cls._execute_generation(client, fallback_model, user_prompt)
                actual_model_used = fallback_model
                fallback_used = True
            except Exception as fb_exc:
                logger.error("Fallback Gemini model '%s' also failed: %s", fallback_model, str(fb_exc))
                raise AIServiceUnavailable(
                    f"Gemini AI Assistant is currently experiencing high demand on both primary and fallback models. "
                    f"Error: {str(last_error or fb_exc)[:100]}"
                )

        if response is None or not response.text:
            logger.error("Gemini returned empty or blocked response across attempts")
            error_detail = f" ({str(last_error)[:100]})" if last_error else ""
            raise AIServiceUnavailable(f"AI analysis service temporarily unavailable{error_detail}.")

        # Parse and validate structured output
        try:
            raw_data = json.loads(response.text)
            validated_pydantic = GrievanceAIAnalysisPydantic(**raw_data)
        except (json.JSONDecodeError, PydanticValidationError) as val_err:
            logger.error("Failed to parse/validate Gemini structured output: %s", str(val_err))
            raise ValidationError("AI model output failed structural validation.")

        analysis_dict = validated_pydantic.model_dump()

        # Business Rule Validation: Priority
        valid_priorities = [p[0] for p in Grievance.Priority.choices]
        if analysis_dict['suggested_priority'].upper() not in valid_priorities:
            logger.warning("Invalid priority '%s' suggested by AI, defaulting to MEDIUM", analysis_dict['suggested_priority'])
            analysis_dict['suggested_priority'] = Grievance.Priority.MEDIUM
        else:
            analysis_dict['suggested_priority'] = analysis_dict['suggested_priority'].upper()

        # Business Rule Validation: Department lookup
        suggested_dept_name = analysis_dict['suggested_department'].strip()
        matched_dept = Department.objects.filter(
            name__iexact=suggested_dept_name,
            is_active=True
        ).first()

        dept_id = None
        dept_code = None
        if matched_dept:
            dept_id = str(matched_dept.id)
            dept_code = matched_dept.code
            analysis_dict['suggested_department'] = matched_dept.name
        else:
            partial_match = Department.objects.filter(
                name__icontains=suggested_dept_name.split()[0],
                is_active=True
            ).first()
            if partial_match:
                dept_id = str(partial_match.id)
                dept_code = partial_match.code
                analysis_dict['suggested_department'] = partial_match.name
            else:
                logger.warning("Suggested department '%s' not recognized in DB", suggested_dept_name)

        analysis_dict['suggested_department_id'] = dept_id
        analysis_dict['suggested_department_code'] = dept_code

        if not analysis_dict.get('summary') or not analysis_dict['summary'].strip():
            analysis_dict['summary'] = subject[:100]

        # Audit metadata tracking model usage and fallback
        metadata = {
            "provider": getattr(settings, 'AI_PROVIDER', 'gemini'),
            "requested_model": primary_model,
            "actual_model": actual_model_used,
            "fallback_used": fallback_used,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION,
            "generation_status": "SUCCESS",
            "validated": True,
        }

        return {
            "suggestions": analysis_dict,
            "metadata": metadata
        }
