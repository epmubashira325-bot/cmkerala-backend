from unittest.mock import patch, MagicMock
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from google.genai.errors import APIError

from accounts.models import User
from departments.models import Department
from grievances.models import Grievance
from ai_assistant.services import GeminiAssistantService, AIServiceUnavailable


class AIAssistantResilienceTests(APITestCase):
    def setUp(self):
        self.dept_pwd = Department.objects.create(name="Public Works Department", code="PWD", is_active=True)
        self.dept_health = Department.objects.create(name="Health Department", code="HLT", is_active=True)
        self.citizen = User.objects.create_citizen(
            email="citizen.resilience@kerala.gov.in",
            password="StrongPassword@123",
            full_name="Resilience Test Citizen"
        )

    # 1. Primary Model Success
    @patch('ai_assistant.services.GeminiAssistantService._execute_generation')
    def test_primary_model_success(self, mock_execute):
        mock_res = MagicMock()
        mock_res.text = '''{
            "suggested_department": "Public Works Department",
            "suggested_category": "Infrastructure",
            "suggested_priority": "HIGH",
            "summary": "Severe pothole hazard on main road.",
            "duplicate_warning": false
        }'''
        mock_execute.return_value = mock_res

        result = GeminiAssistantService.analyze_grievance(
            subject="Damaged bridge road",
            description="Deep potholes and structural cracks on bridge road in Palakkad.",
            district="PALAKKAD"
        )

        self.assertEqual(result["metadata"]["requested_model"], "gemini-3.6-flash")
        self.assertEqual(result["metadata"]["actual_model"], "gemini-3.6-flash")
        self.assertFalse(result["metadata"]["fallback_used"])
        self.assertEqual(result["metadata"]["generation_status"], "SUCCESS")
        self.assertEqual(result["suggestions"]["suggested_department_code"], "PWD")

    # 2. Primary Failure with Successful Fallback
    @override_settings(GEMINI_FALLBACK_MODEL="gemini-3.8-flash")
    @patch('ai_assistant.services.GeminiAssistantService._execute_generation')
    def test_primary_failure_with_successful_fallback(self, mock_execute):
        mock_res_fallback = MagicMock()
        mock_res_fallback.text = '''{
            "suggested_department": "Health Department",
            "suggested_category": "Healthcare & Medical",
            "suggested_priority": "MEDIUM",
            "summary": "Hospital medicine shortage reported.",
            "duplicate_warning": false
        }'''

        # Primary raises 503 high demand; Fallback succeeds
        err_503 = APIError(503, {"error": {"message": "High demand on primary"}})
        mock_execute.side_effect = [err_503, mock_res_fallback]

        result = GeminiAssistantService.analyze_grievance(
            subject="PHC medicine shortage",
            description="Essential insulin and antibiotics are out of stock at the PHC.",
            district="KOLLAM"
        )

        self.assertEqual(result["metadata"]["requested_model"], "gemini-3.6-flash")
        self.assertEqual(result["metadata"]["actual_model"], "gemini-3.8-flash")
        self.assertTrue(result["metadata"]["fallback_used"])
        self.assertEqual(result["metadata"]["generation_status"], "SUCCESS")
        self.assertEqual(result["suggestions"]["suggested_department_code"], "HLT")

    # 3. Both Models Unavailable
    @override_settings(GEMINI_FALLBACK_MODEL="gemini-3.8-flash")
    @patch('ai_assistant.services.GeminiAssistantService._execute_generation')
    def test_both_models_unavailable(self, mock_execute):
        err_503 = APIError(503, {"error": {"message": "High demand"}})
        err_504 = APIError(504, {"error": {"message": "Deadline exceeded"}})
        mock_execute.side_effect = [err_503, err_504]

        with self.assertRaises(AIServiceUnavailable) as ctx:
            GeminiAssistantService.analyze_grievance(
                subject="Road issue",
                description="Long description exceeding minimum character constraints.",
                district="WAYANAD"
            )
        self.assertIn("high demand on both primary and fallback", str(ctx.exception))

    # 4. Invalid API Key
    @override_settings(GEMINI_API_KEY="")
    def test_invalid_api_key_raises_immediately(self):
        with self.assertRaises(AIServiceUnavailable):
            GeminiAssistantService.get_client()

    # 5. Malformed Structured Output
    @patch('ai_assistant.services.GeminiAssistantService._execute_generation')
    def test_malformed_structured_output_rejection(self, mock_execute):
        mock_res = MagicMock()
        mock_res.text = "NOT_A_JSON_RESPONSE"
        mock_execute.return_value = mock_res

        with self.assertRaises(Exception):
            GeminiAssistantService.analyze_grievance(
                subject="Streetlight repair",
                description="Streetlight has been out of order for weeks.",
                district="KANNUR"
            )

    # 6. Model Information Saved Correctly in Endpoint
    @patch('ai_assistant.services.GeminiAssistantService.analyze_grievance')
    def test_endpoint_returns_model_audit_metadata(self, mock_analyze):
        mock_analyze.return_value = {
            "suggestions": {
                "suggested_department": "Public Works Department",
                "suggested_department_id": str(self.dept_pwd.id),
                "suggested_department_code": "PWD",
                "suggested_category": "Infrastructure",
                "suggested_priority": "HIGH",
                "summary": "Damaged road causing traffic issues.",
                "duplicate_warning": False
            },
            "metadata": {
                "provider": "gemini",
                "requested_model": "gemini-3.6-flash",
                "actual_model": "gemini-3.8-flash",
                "fallback_used": True,
                "analysis_timestamp": "2026-11-12T13:00:00Z",
                "prompt_version": "1.0.0",
                "generation_status": "SUCCESS",
                "validated": True
            }
        }

        self.client.force_authenticate(user=self.citizen)
        payload = {
            "subject": "Damaged bridge road",
            "description": "The approach road to the bridge has collapsed due to heavy rainfall.",
            "district": "PALAKKAD"
        }
        res = self.client.post('/api/v1/ai/analyze/', payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        meta = res.data["metadata"]
        self.assertEqual(meta["requested_model"], "gemini-3.6-flash")
        self.assertEqual(meta["actual_model"], "gemini-3.8-flash")
        self.assertTrue(meta["fallback_used"])

    # 7. Existing Grievance Submission Fallback
    @patch('ai_assistant.services.GeminiAssistantService.analyze_grievance')
    def test_grievance_submission_fallback_on_ai_failure(self, mock_analyze):
        mock_analyze.side_effect = AIServiceUnavailable("Outage")

        self.client.force_authenticate(user=self.citizen)
        payload = {
            "district": "KOZHIKODE",
            "category": "Infrastructure",
            "subject": "Broken canal wall",
            "description": "Irrigation canal wall has collapsed threatening nearby houses.",
            "priority": "HIGH",
            "include_ai_triage": True
        }
        res = self.client.post('/api/v1/citizen/grievances/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        g = Grievance.objects.get(reference_number=res.data['reference_number'])
        self.assertEqual(g.ai_metadata.get('status'), 'skipped_or_failed')

    # -------------------------------------------------------------------------
    # RESTORED MISSING TESTS (BRINGING SUITE TO 10 IN AI_ASSISTANT / 23 TOTAL)
    # -------------------------------------------------------------------------

    # 8. Unrecognized Department Suggestion
    @patch('ai_assistant.services.GeminiAssistantService._execute_generation')
    def test_unrecognized_department_suggestion(self, mock_execute):
        mock_res = MagicMock()
        mock_res.text = '''{
            "suggested_department": "Fictional Department of Space Exploration",
            "suggested_category": "General",
            "suggested_priority": "LOW",
            "summary": "Inquiry regarding rocket launching facility.",
            "duplicate_warning": false
        }'''
        mock_execute.return_value = mock_res

        result = GeminiAssistantService.analyze_grievance(
            subject="Space exploration enquiry",
            description="Citizen asking for space rocket facility details in Idukki.",
            district="IDUKKI"
        )

        s = result["suggestions"]
        self.assertEqual(s["suggested_department"], "Fictional Department of Space Exploration")
        self.assertIsNone(s["suggested_department_id"])
        self.assertIsNone(s["suggested_department_code"])

    # 9. Invalid Priority Normalization
    @patch('ai_assistant.services.GeminiAssistantService._execute_generation')
    def test_invalid_priority_normalization(self, mock_execute):
        mock_res = MagicMock()
        # Invalid priority 'CRITICAL'
        mock_res.text = '''{
            "suggested_department": "Health Department",
            "suggested_category": "Healthcare & Medical",
            "suggested_priority": "CRITICAL",
            "summary": "Acute ambulance shortage.",
            "duplicate_warning": false
        }'''
        mock_execute.return_value = mock_res

        result = GeminiAssistantService.analyze_grievance(
            subject="Ambulance shortage",
            description="No ambulances are available at the taluk hospital for emergency transfers.",
            district="KASARAGOD"
        )

        # Must safely default to MEDIUM without failing
        self.assertEqual(result["suggestions"]["suggested_priority"], "MEDIUM")

    # 10. CMO Human Override of AI Suggestions
    def test_cmo_human_override_of_ai_suggestions(self):
        dept_revenue = Department.objects.create(name="Revenue Department", code="REV", is_active=True)
        cmo_admin = User.objects.create_superuser(
            email="cmo.override@kerala.gov.in",
            password="AdminPassword@123",
            full_name="CMO Supervisor"
        )

        # Grievance with AI suggesting PWD
        g = Grievance.objects.create(
            citizen=self.citizen,
            district=Grievance.District.ALAPPUZHA,
            category="Infrastructure",
            subject="Land survey dispute on bypass",
            description="Dispute over boundary demarcation on newly constructed bypass road.",
            priority=Grievance.Priority.MEDIUM,
            ai_suggestions={
                "suggested_department": "Public Works Department",
                "suggested_department_code": "PWD",
                "suggested_priority": "HIGH"
            },
            ai_metadata={"model": "gemini-3.6-flash"}
        )

        self.client.force_authenticate(user=cmo_admin)
        override_payload = {
            "department_id": str(dept_revenue.id),
            "remarks": "CMO Override: Boundary survey dispute strictly falls under Revenue Department jurisdiction."
        }
        res = self.client.post(f'/api/v1/cmo/grievances/{g.id}/assign/', override_payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        g.refresh_from_db()
        # Administrator-approved assignment is updated
        self.assertEqual(g.assigned_department, dept_revenue)
        # Original AI suggestions are preserved intact
        self.assertEqual(g.ai_suggestions["suggested_department"], "Public Works Department")
        self.assertEqual(g.ai_suggestions["suggested_priority"], "HIGH")
