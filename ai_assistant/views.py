import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiResponse

from accounts.permissions import IsCitizen
from .serializers import (
    AIAnalyzeRequestSerializer,
    AIAnalyzeResponseSerializer,
)
from .services import GeminiAssistantService

logger = logging.getLogger(__name__)


class AIAnalysisRateThrottle(UserRateThrottle):
    """
    Limits citizens to 15 AI triage requests per minute to prevent quota exhaustion and spam.
    """
    rate = '15/min'


class AIAnalyzeGrievanceView(APIView):
    """
    POST /api/v1/ai/analyze/

    Analyzes citizen complaint draft using Google Gemini structured model output.
    Returns:
    - Recommended Department
    - Recommended Category
    - Priority classification (LOW, MEDIUM, HIGH)
    - Executive summary for CMO review
    - Duplicate detection flag
    """
    permission_classes = [IsAuthenticated, IsCitizen]
    throttle_classes = [AIAnalysisRateThrottle]
    serializer_class = AIAnalyzeResponseSerializer

    @extend_schema(
        summary="Citizen: Analyze grievance draft using Google Gemini AI",
        description=(
            "Provides automated triage suggestions for complaint category, priority level, "
            "and department routing. Suggestions are advisory and can be reviewed before submission."
        ),
        request=AIAnalyzeRequestSerializer,
        responses={
            200: AIAnalyzeResponseSerializer,
            400: OpenApiResponse(description="Invalid request fields"),
            429: OpenApiResponse(description="Rate limit exceeded"),
            503: OpenApiResponse(description="AI service temporarily unavailable (fallback to manual submission)"),
        }
    )
    def post(self, request):
        req_serializer = AIAnalyzeRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)

        data = req_serializer.validated_data
        result = GeminiAssistantService.analyze_grievance(
            subject=data['subject'],
            description=data['description'],
            district=data['district']
        )

        response_payload = {
            "suggestions": result["suggestions"],
            "metadata": result["metadata"],
            "message": "AI analysis completed successfully."
        }

        res_serializer = AIAnalyzeResponseSerializer(data=response_payload)
        res_serializer.is_valid(raise_exception=True)
        return Response(res_serializer.data, status=status.HTTP_200_OK)
