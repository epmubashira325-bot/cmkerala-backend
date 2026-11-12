from rest_framework import serializers
from django.db import transaction
from .models import (
    Grievance,
    GrievanceHistory,
    DepartmentAssignment,
    GrievanceAttachment,
    ActionTakenReport,
    CitizenFeedback,
)
from accounts.serializers import UserPublicSerializer
from departments.serializers import DepartmentSerializer
from departments.models import Department
from accounts.models import User


class GrievanceAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)

    class Meta:
        model = GrievanceAttachment
        fields = (
            'id',
            'file',
            'original_filename',
            'file_type',
            'file_size',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
        )
        read_only_fields = ('id', 'original_filename', 'file_type', 'file_size', 'uploaded_by', 'created_at')


class GrievanceHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True)
    changed_by_role = serializers.CharField(source='changed_by.role', read_only=True)

    class Meta:
        model = GrievanceHistory
        fields = (
            'id',
            'previous_status',
            'new_status',
            'changed_by',
            'changed_by_name',
            'changed_by_role',
            'remarks',
            'created_at',
        )
        read_only_fields = fields


class DepartmentAssignmentSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    officer_name = serializers.CharField(source='officer.full_name', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True)

    class Meta:
        model = DepartmentAssignment
        fields = (
            'id',
            'department',
            'department_name',
            'department_code',
            'officer',
            'officer_name',
            'assigned_by',
            'assigned_by_name',
            'assigned_at',
            'due_date',
            'is_active',
            'ended_at',
        )
        read_only_fields = fields


class ActionTakenReportSerializer(serializers.ModelSerializer):
    officer_name = serializers.CharField(source='officer.full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.full_name', read_only=True)

    class Meta:
        model = ActionTakenReport
        fields = (
            'id',
            'grievance',
            'officer',
            'officer_name',
            'investigation_description',
            'resolution_details',
            'report_attachment',
            'review_status',
            'reviewed_by',
            'reviewed_by_name',
            'review_remarks',
            'submitted_at',
            'reviewed_at',
        )
        read_only_fields = (
            'id',
            'grievance',
            'officer',
            'review_status',
            'reviewed_by',
            'review_remarks',
            'submitted_at',
            'reviewed_at',
        )


class CitizenFeedbackSerializer(serializers.ModelSerializer):
    citizen_name = serializers.CharField(source='citizen.full_name', read_only=True)

    class Meta:
        model = CitizenFeedback
        fields = (
            'id',
            'grievance',
            'citizen',
            'citizen_name',
            'rating',
            'comments',
            'created_at',
        )
        read_only_fields = ('id', 'grievance', 'citizen', 'created_at')

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be an integer between 1 and 5.")
        return value


class GrievanceListSerializer(serializers.ModelSerializer):
    citizen_name = serializers.CharField(source='citizen.full_name', read_only=True)
    assigned_department_code = serializers.CharField(source='assigned_department.code', read_only=True)
    assigned_department_name = serializers.CharField(source='assigned_department.name', read_only=True)
    assigned_officer_name = serializers.CharField(source='assigned_officer.full_name', read_only=True)

    class Meta:
        model = Grievance
        fields = (
            'id',
            'reference_number',
            'citizen',
            'citizen_name',
            'district',
            'category',
            'subject',
            'priority',
            'status',
            'assigned_department',
            'assigned_department_code',
            'assigned_department_name',
            'assigned_officer',
            'assigned_officer_name',
            'due_date',
            'is_escalated',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class GrievanceDetailSerializer(serializers.ModelSerializer):
    citizen = UserPublicSerializer(read_only=True)
    assigned_department = DepartmentSerializer(read_only=True)
    assigned_officer = UserPublicSerializer(read_only=True)
    attachments = GrievanceAttachmentSerializer(many=True, read_only=True)
    history_logs = GrievanceHistorySerializer(many=True, read_only=True)
    assignments = DepartmentAssignmentSerializer(many=True, read_only=True)
    action_reports = ActionTakenReportSerializer(many=True, read_only=True)
    feedback = CitizenFeedbackSerializer(read_only=True)

    class Meta:
        model = Grievance
        fields = (
            'id',
            'reference_number',
            'citizen',
            'district',
            'category',
            'subject',
            'description',
            'priority',
            'status',
            'assigned_department',
            'assigned_officer',
            'ai_suggestions',
            'ai_metadata',
            'due_date',
            'is_escalated',
            'attachments',
            'history_logs',
            'assignments',
            'action_reports',
            'feedback',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class CitizenGrievanceCreateSerializer(serializers.ModelSerializer):
    attachments = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False),
        write_only=True,
        required=False
    )

    include_ai_triage = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="If True, automatically requests Gemini AI triage and links suggestions to the grievance."
    )

    class Meta:
        model = Grievance
        fields = (
            'id',
            'reference_number',
            'district',
            'category',
            'subject',
            'description',
            'priority',
            'status',
            'attachments',
            'include_ai_triage',
            'ai_suggestions',
            'ai_metadata',
            'created_at',
        )
        read_only_fields = ('id', 'reference_number', 'status', 'ai_suggestions', 'ai_metadata', 'created_at')

    def validate_district(self, value):
        valid_districts = [choice[0] for choice in Grievance.District.choices]
        if value.upper() not in valid_districts:
            raise serializers.ValidationError(f"Invalid Kerala district. Must be one of: {', '.join(valid_districts)}")
        return value.upper()

    def validate_subject(self, value):
        val = value.strip()
        if len(val) < 5:
            raise serializers.ValidationError("Subject must be at least 5 characters long.")
        return val

    def validate_description(self, value):
        val = value.strip()
        if len(val) < 15:
            raise serializers.ValidationError("Description must be at least 15 characters long.")
        return val

    @transaction.atomic
    def create(self, validated_data):
        attachments_data = validated_data.pop('attachments', [])
        include_ai = validated_data.pop('include_ai_triage', False)
        user = self.context['request'].user
        validated_data['citizen'] = user
        validated_data['status'] = Grievance.Status.SUBMITTED

        # Perform AI triage if citizen opted in or requested
        if include_ai:
            try:
                from ai_assistant.services import GeminiAssistantService
                ai_result = GeminiAssistantService.analyze_grievance(
                    subject=validated_data['subject'],
                    description=validated_data['description'],
                    district=validated_data['district']
                )
                validated_data['ai_suggestions'] = ai_result['suggestions']
                validated_data['ai_metadata'] = ai_result['metadata']
            except Exception as e:
                # Resilient fallback: Never block grievance creation if AI service is down
                import logging
                logging.getLogger(__name__).warning("AI triage failed during grievance submission: %s", str(e))
                validated_data['ai_suggestions'] = {}
                validated_data['ai_metadata'] = {"status": "skipped_or_failed", "error": str(e)[:100]}

        grievance = Grievance.objects.create(**validated_data)

        # Create initial immutable history log
        GrievanceHistory.objects.create(
            grievance=grievance,
            previous_status=Grievance.Status.SUBMITTED,
            new_status=Grievance.Status.SUBMITTED,
            changed_by=user,
            remarks="Grievance filed by citizen."
        )

        # Handle attachment files
        for uploaded_file in attachments_data:
            GrievanceAttachment.objects.create(
                grievance=grievance,
                uploaded_by=user,
                file=uploaded_file,
                original_filename=uploaded_file.name,
                file_type=getattr(uploaded_file, 'content_type', 'application/octet-stream'),
                file_size=uploaded_file.size
            )

        return grievance


class PublicGrievanceTrackSerializer(serializers.ModelSerializer):
    """
    Public tracking serializer with ZERO private citizen credentials or sensitive info.
    """
    department_name = serializers.CharField(source='assigned_department.name', read_only=True)

    class Meta:
        model = Grievance
        fields = (
            'reference_number',
            'status',
            'priority',
            'district',
            'category',
            'department_name',
            'due_date',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class AssignDepartmentSerializer(serializers.Serializer):
    department_id = serializers.UUIDField(required=True)
    officer_id = serializers.UUIDField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        dept_id = attrs.get('department_id')
        try:
            dept = Department.objects.get(id=dept_id, is_active=True)
            attrs['department'] = dept
        except Department.DoesNotExist:
            raise serializers.ValidationError({"department_id": "Active department with this ID does not exist."})

        officer_id = attrs.get('officer_id')
        if officer_id:
            try:
                officer = User.objects.get(id=officer_id, role=User.Role.OFFICER, is_active=True)
                if officer.department_id != dept.id:
                    raise serializers.ValidationError({
                        "officer_id": f"Officer '{officer.full_name}' does not belong to '{dept.name}'."
                    })
                attrs['officer'] = officer
            except User.DoesNotExist:
                raise serializers.ValidationError({"officer_id": "Active officer with this ID does not exist."})
        else:
            attrs['officer'] = None

        return attrs


class RemarkSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=True, min_length=3)


class EscalateSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, default="Escalated due to SLA breach.")


class ReviewATRSerializer(serializers.Serializer):
    decision = serializers.ChoiceFilter() if False else serializers.ChoiceField(
        choices=[ActionTakenReport.ReviewStatus.APPROVED, ActionTakenReport.ReviewStatus.REJECTED]
    )
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

