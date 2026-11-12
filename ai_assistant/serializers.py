from rest_framework import serializers
from grievances.models import Grievance


class AIAnalyzeRequestSerializer(serializers.Serializer):
    """
    Request serializer for complaint triage analysis.
    """
    subject = serializers.CharField(
        required=True,
        min_length=5,
        max_length=255,
        help_text="Subject or title of the citizen complaint."
    )
    description = serializers.CharField(
        required=True,
        min_length=15,
        max_length=5000,
        help_text="Detailed complaint description."
    )
    district = serializers.ChoiceField(
        choices=Grievance.District.choices,
        required=True,
        help_text="One of the 14 revenue districts of Kerala."
    )


class AISuggestionsSerializer(serializers.Serializer):
    suggested_department = serializers.CharField(allow_blank=True, required=False)
    suggested_department_id = serializers.UUIDField(allow_null=True, required=False)
    suggested_department_code = serializers.CharField(allow_null=True, required=False)
    suggested_category = serializers.CharField()
    suggested_priority = serializers.ChoiceField(choices=Grievance.Priority.choices)
    summary = serializers.CharField()
    duplicate_warning = serializers.BooleanField(default=False)


class AIMetadataSerializer(serializers.Serializer):
    provider = serializers.CharField()
    requested_model = serializers.CharField(required=False)
    actual_model = serializers.CharField(required=False)
    fallback_used = serializers.BooleanField(required=False, default=False)
    analysis_timestamp = serializers.CharField(required=False)
    prompt_version = serializers.CharField()
    generation_status = serializers.CharField(required=False, default="SUCCESS")
    validated = serializers.BooleanField(required=False, default=True)


class AIAnalyzeResponseSerializer(serializers.Serializer):
    suggestions = AISuggestionsSerializer()
    metadata = AIMetadataSerializer()
    message = serializers.CharField(default="AI analysis completed successfully.")

