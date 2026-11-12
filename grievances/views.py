from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError, PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from .models import (
    Grievance,
    GrievanceHistory,
    DepartmentAssignment,
    GrievanceAttachment,
    ActionTakenReport,
    CitizenFeedback,
)
from .serializers import (
    GrievanceListSerializer,
    GrievanceDetailSerializer,
    CitizenGrievanceCreateSerializer,
    PublicGrievanceTrackSerializer,
    AssignDepartmentSerializer,
    RemarkSerializer,
    EscalateSerializer,
    ReviewATRSerializer,
    ActionTakenReportSerializer,
    CitizenFeedbackSerializer,
    DepartmentAssignmentSerializer,
)
from .filters import GrievanceFilter
from .services import GrievanceWorkflowService
from accounts.permissions import (
    IsCitizen,
    IsCMOAdmin,
    IsOfficer,
    IsGrievanceOwner,
    IsAssignedOfficer,
)


# ============================================================================
# CITIZEN GRIEVANCE VIEWS
# ============================================================================

class CitizenGrievanceListCreateView(generics.ListCreateAPIView):
    """
    List citizen's own grievances or submit a new grievance with optional attachments.
    """
    permission_classes = [IsCitizen]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = GrievanceFilter
    search_fields = ['reference_number', 'subject', 'description', 'category']
    ordering_fields = ['created_at', 'priority', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Grievance.objects.none()
        return Grievance.objects.filter(citizen=self.request.user).select_related(
            'assigned_department', 'assigned_officer'
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CitizenGrievanceCreateSerializer
        return GrievanceListSerializer

    @extend_schema(summary="Citizen: Submit a new grievance")
    def post(self, request, *args, **kwargs):
        serializer = CitizenGrievanceCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        grievance = serializer.save()
        return Response(
            GrievanceDetailSerializer(grievance).data,
            status=status.HTTP_201_CREATED
        )


class CitizenGrievanceDetailView(generics.RetrieveAPIView):
    """
    Retrieve full details and history for a citizen's own grievance.
    """
    serializer_class = GrievanceDetailSerializer
    permission_classes = [IsCitizen, IsGrievanceOwner]

    def get_queryset(self):
        return Grievance.objects.filter(citizen=self.request.user).select_related(
            'citizen', 'assigned_department', 'assigned_officer'
        ).prefetch_related(
            'attachments', 'history_logs__changed_by', 'assignments__department',
            'action_reports__officer', 'feedback'
        )


class PublicGrievanceTrackView(APIView):
    """
    Public tracking by reference number. Exposes zero private citizen data.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Public: Track grievance status by reference number",
        parameters=[
            OpenApiParameter(name='ref', description='Grievance reference number (e.g. CMK-20261112-XXXXXXXX)', required=True, type=str)
        ],
        responses={200: PublicGrievanceTrackSerializer, 404: OpenApiResponse(description="Reference number not found")}
    )
    def get(self, request):
        ref = request.query_params.get('ref', '').strip()
        if not ref:
            return Response(
                {"detail": "Please provide a valid 'ref' parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            grievance = Grievance.objects.select_related('assigned_department').get(reference_number__iexact=ref)
            serializer = PublicGrievanceTrackSerializer(grievance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Grievance.DoesNotExist:
            return Response(
                {"detail": f"No grievance found with reference number '{ref}'."},
                status=status.HTTP_404_NOT_FOUND
            )


# ============================================================================
# CMO ADMIN VIEWS
# ============================================================================

class CMOGrievanceListView(generics.ListAPIView):
    """
    CMO: View and filter all citizen grievances across all departments and districts.
    """
    serializer_class = GrievanceListSerializer
    permission_classes = [IsCMOAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = GrievanceFilter
    search_fields = ['reference_number', 'subject', 'description', 'citizen__email', 'citizen__full_name']
    ordering_fields = ['created_at', 'priority', 'status', 'due_date']
    ordering = ['-created_at']

    def get_queryset(self):
        return Grievance.objects.all().select_related(
            'citizen', 'assigned_department', 'assigned_officer'
        )


class CMOGrievanceDetailView(generics.RetrieveAPIView):
    """
    CMO: View complete details, attachments, history logs, and ATRs for any grievance.
    """
    serializer_class = GrievanceDetailSerializer
    permission_classes = [IsCMOAdmin]
    queryset = Grievance.objects.all().select_related(
        'citizen', 'assigned_department', 'assigned_officer'
    ).prefetch_related(
        'attachments', 'history_logs__changed_by', 'assignments__department',
        'assignments__officer', 'action_reports__officer', 'feedback'
    )


class CMOAssignGrievanceView(APIView):
    """
    CMO: Assign or reassign grievance to a department and/or specific officer.
    """
    permission_classes = [IsCMOAdmin]
    serializer_class = AssignDepartmentSerializer

    @extend_schema(summary="CMO: Assign grievance to department and officer", request=AssignDepartmentSerializer)
    def post(self, request, pk):
        try:
            grievance = Grievance.objects.get(pk=pk)
        except Grievance.DoesNotExist:
            return Response({"detail": "Grievance not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AssignDepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment = GrievanceWorkflowService.assign_department_and_officer(
            grievance=grievance,
            department=serializer.validated_data['department'],
            officer=serializer.validated_data.get('officer'),
            assigned_by=request.user,
            due_date=serializer.validated_data.get('due_date'),
            remarks=serializer.validated_data.get('remarks', '')
        )

        return Response(
            {
                "message": "Department assignment recorded successfully.",
                "assignment": DepartmentAssignmentSerializer(assignment).data,
                "current_status": grievance.status
            },
            status=status.HTTP_200_OK
        )


class CMOAddRemarkView(APIView):
    """
    CMO: Add internal remark or observation to grievance history.
    """
    permission_classes = [IsCMOAdmin]
    serializer_class = RemarkSerializer

    @extend_schema(summary="CMO: Add internal remark to grievance history", request=RemarkSerializer)
    def post(self, request, pk):
        try:
            grievance = Grievance.objects.get(pk=pk)
        except Grievance.DoesNotExist:
            return Response({"detail": "Grievance not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RemarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        remarks = serializer.validated_data['remarks']
        history = GrievanceHistory.objects.create(
            grievance=grievance,
            previous_status=grievance.status,
            new_status=grievance.status,
            changed_by=request.user,
            remarks=f"[CMO Note] {remarks}"
        )

        return Response(
            {"message": "Remark recorded in grievance history.", "history_id": history.id},
            status=status.HTTP_200_OK
        )


class CMOEscalateView(APIView):
    """
    CMO: Flag grievance as escalated.
    """
    permission_classes = [IsCMOAdmin]
    serializer_class = EscalateSerializer

    @extend_schema(summary="CMO: Escalate grievance", request=EscalateSerializer)
    def post(self, request, pk):
        try:
            grievance = Grievance.objects.get(pk=pk)
        except Grievance.DoesNotExist:
            return Response({"detail": "Grievance not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EscalateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        grievance.is_escalated = True
        grievance.save(update_fields=['is_escalated', 'updated_at'])

        GrievanceHistory.objects.create(
            grievance=grievance,
            previous_status=grievance.status,
            new_status=grievance.status,
            changed_by=request.user,
            remarks=f"[ESCALATION] {serializer.validated_data.get('remarks', 'Escalated by CMO')}"
        )

        return Response(
            {"message": "Grievance successfully escalated to CMO priority queue."},
            status=status.HTTP_200_OK
        )


class CMOReviewReportView(APIView):
    """
    CMO: Review Action Taken Report filed by officer. Approves or rejects report.
    """
    permission_classes = [IsCMOAdmin]
    serializer_class = ReviewATRSerializer

    @extend_schema(summary="CMO: Review and Approve/Reject Action Taken Report", request=ReviewATRSerializer)
    def post(self, request, pk):
        try:
            report = ActionTakenReport.objects.select_related('grievance', 'officer').get(pk=pk)
        except ActionTakenReport.DoesNotExist:
            return Response({"detail": "Action Taken Report not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReviewATRSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_report = GrievanceWorkflowService.review_action_taken_report(
            report=report,
            cmo_admin=request.user,
            decision=serializer.validated_data['decision'],
            remarks=serializer.validated_data.get('remarks', '')
        )

        return Response(
            {
                "message": f"Report successfully marked as {updated_report.review_status}.",
                "report": ActionTakenReportSerializer(updated_report).data,
                "grievance_status": updated_report.grievance.status
            },
            status=status.HTTP_200_OK
        )


# ============================================================================
# OFFICER GRIEVANCE VIEWS
# ============================================================================

class OfficerGrievanceListView(generics.ListAPIView):
    """
    Officer: List only grievances assigned to the logged-in officer or their department.
    """
    serializer_class = GrievanceListSerializer
    permission_classes = [IsOfficer]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = GrievanceFilter
    search_fields = ['reference_number', 'subject', 'description']
    ordering_fields = ['created_at', 'priority', 'status', 'due_date']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False) or not user.is_authenticated or not hasattr(user, 'department'):
            return Grievance.objects.none()
        return Grievance.objects.filter(
            Q(assigned_officer=user) |
            Q(assigned_department=user.department, assigned_officer__isnull=True)
        ).select_related('citizen', 'assigned_department', 'assigned_officer')


class OfficerGrievanceDetailView(generics.RetrieveAPIView):
    """
    Officer: Retrieve details for an authorized assigned grievance.
    """
    serializer_class = GrievanceDetailSerializer
    permission_classes = [IsOfficer, IsAssignedOfficer]

    def get_queryset(self):
        user = self.request.user
        return Grievance.objects.filter(
            Q(assigned_officer=user) |
            Q(assigned_department=user.department, assigned_officer__isnull=True)
        ).select_related(
            'citizen', 'assigned_department', 'assigned_officer'
        ).prefetch_related(
            'attachments', 'history_logs__changed_by', 'action_reports__officer'
        )


class OfficerAddRemarkView(APIView):
    """
    Officer: Record investigation note on an assigned grievance.
    Automatically moves grievance to IN_PROGRESS if currently UNDER_REVIEW.
    """
    permission_classes = [IsOfficer, IsAssignedOfficer]
    serializer_class = RemarkSerializer

    @extend_schema(summary="Officer: Record investigation remarks", request=RemarkSerializer)
    def post(self, request, pk):
        try:
            grievance = Grievance.objects.get(pk=pk)
        except Grievance.DoesNotExist:
            return Response({"detail": "Grievance not found."}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, grievance)

        serializer = RemarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        remarks = serializer.validated_data['remarks']

        # Transition status to IN_PROGRESS if currently UNDER_REVIEW
        if grievance.status == Grievance.Status.UNDER_REVIEW:
            GrievanceWorkflowService.change_status(
                grievance=grievance,
                new_status=Grievance.Status.IN_PROGRESS,
                actor=request.user,
                remarks=f"[Investigation Note] {remarks}"
            )
        else:
            GrievanceHistory.objects.create(
                grievance=grievance,
                previous_status=grievance.status,
                new_status=grievance.status,
                changed_by=request.user,
                remarks=f"[Investigation Note] {remarks}"
            )

        return Response(
            {"message": "Investigation remark saved.", "status": grievance.status},
            status=status.HTTP_200_OK
        )


class OfficerSubmitReportView(APIView):
    """
    Officer: Submit Action Taken Report (ATR) for CMO review.
    """
    permission_classes = [IsOfficer, IsAssignedOfficer]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = ActionTakenReportSerializer

    @extend_schema(summary="Officer: Submit Action Taken Report (ATR)", request=ActionTakenReportSerializer)
    def post(self, request, pk):
        try:
            grievance = Grievance.objects.get(pk=pk)
        except Grievance.DoesNotExist:
            return Response({"detail": "Grievance not found."}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, grievance)

        investigation_desc = request.data.get('investigation_description', '').strip()
        resolution_details = request.data.get('resolution_details', '').strip()
        report_file = request.FILES.get('report_attachment')

        if not investigation_desc or len(investigation_desc) < 10:
            raise ValidationError({"investigation_description": "Investigation description must be at least 10 characters."})
        if not resolution_details or len(resolution_details) < 10:
            raise ValidationError({"resolution_details": "Resolution details must be at least 10 characters."})

        # Create ATR with PENDING review status
        atr = ActionTakenReport.objects.create(
            grievance=grievance,
            officer=request.user,
            investigation_description=investigation_desc,
            resolution_details=resolution_details,
            report_attachment=report_file,
            review_status=ActionTakenReport.ReviewStatus.PENDING
        )

        # Record submission in audit history
        GrievanceHistory.objects.create(
            grievance=grievance,
            previous_status=grievance.status,
            new_status=grievance.status,
            changed_by=request.user,
            remarks="Action Taken Report (ATR) submitted by officer. Awaiting CMO review."
        )

        return Response(
            {
                "message": "Action Taken Report submitted successfully for CMO review.",
                "report": ActionTakenReportSerializer(atr).data
            },
            status=status.HTTP_201_CREATED
        )


# ============================================================================
# CITIZEN FEEDBACK VIEW
# ============================================================================

class CitizenFeedbackSubmitView(APIView):
    """
    Submit feedback rating for a resolved grievance.
    """
    permission_classes = [IsCitizen, IsGrievanceOwner]
    serializer_class = CitizenFeedbackSerializer

    @extend_schema(summary="Citizen: Submit satisfaction feedback for resolved grievance", request=CitizenFeedbackSerializer)
    def post(self, request, pk):
        try:
            grievance = Grievance.objects.get(pk=pk)
        except Grievance.DoesNotExist:
            return Response({"detail": "Grievance not found."}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, grievance)

        if grievance.status != Grievance.Status.RESOLVED:
            raise ValidationError({"detail": "Feedback can only be provided for RESOLVED grievances."})

        if hasattr(grievance, 'feedback'):
            raise ValidationError({"detail": "Feedback has already been submitted for this grievance."})

        serializer = CitizenFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feedback = CitizenFeedback.objects.create(
            grievance=grievance,
            citizen=request.user,
            rating=serializer.validated_data['rating'],
            comments=serializer.validated_data.get('comments', '')
        )

        return Response(
            {
                "message": "Thank you for your feedback.",
                "feedback": CitizenFeedbackSerializer(feedback).data
            },
            status=status.HTTP_201_CREATED
        )
