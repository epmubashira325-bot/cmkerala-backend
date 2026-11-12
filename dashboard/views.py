from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from accounts.permissions import IsCMOAdmin
from grievances.models import Grievance
from departments.models import Department


from .serializers import CMODashboardStatsResponseSerializer


class CMODashboardStatsView(APIView):
    """
    Live aggregated statistics for CMO executive dashboard.
    Computes total counts, status breakdown, SLA breaches, and distributions across
    Kerala's 14 districts, government departments, and priority levels.
    """
    permission_classes = [IsCMOAdmin]
    serializer_class = CMODashboardStatsResponseSerializer

    @extend_schema(
        summary="CMO: Retrieve comprehensive dashboard metrics and distributions",
        responses={200: CMODashboardStatsResponseSerializer}
    )
    def get(self, request):
        today = timezone.now().date()

        # Core status counts and overdue metrics
        aggregates = Grievance.objects.aggregate(
            total=Count('id'),
            submitted=Count('id', filter=Q(status=Grievance.Status.SUBMITTED)),
            under_review=Count('id', filter=Q(status=Grievance.Status.UNDER_REVIEW)),
            in_progress=Count('id', filter=Q(status=Grievance.Status.IN_PROGRESS)),
            resolved=Count('id', filter=Q(status=Grievance.Status.RESOLVED)),
            reopened=Count('id', filter=Q(status=Grievance.Status.REOPENED)),
            overdue=Count(
                'id',
                filter=~Q(status=Grievance.Status.RESOLVED) & Q(due_date__isnull=False) & Q(due_date__lt=today)
            ),
            escalated=Count('id', filter=Q(is_escalated=True)),
        )

        # Priority breakdown
        priority_data = Grievance.objects.values('priority').annotate(
            count=Count('id')
        ).order_by('priority')
        priority_distribution = {item['priority']: item['count'] for item in priority_data}

        # District-wise distribution (Kerala 14 districts)
        district_data = Grievance.objects.values('district').annotate(
            count=Count('id')
        ).order_by('-count')
        district_distribution = [
            {'district': item['district'], 'count': item['count']} for item in district_data
        ]

        # Department-wise distribution
        dept_data = Department.objects.filter(is_active=True).annotate(
            total_grievances=Count('assigned_grievances'),
            pending_grievances=Count(
                'assigned_grievances',
                filter=~Q(assigned_grievances__status=Grievance.Status.RESOLVED)
            ),
            resolved_grievances=Count(
                'assigned_grievances',
                filter=Q(assigned_grievances__status=Grievance.Status.RESOLVED)
            )
        ).values('id', 'name', 'code', 'total_grievances', 'pending_grievances', 'resolved_grievances').order_by('-total_grievances')

        return Response({
            'overview': {
                'total_grievances': aggregates['total'],
                'submitted': aggregates['submitted'],
                'under_review': aggregates['under_review'],
                'in_progress': aggregates['in_progress'],
                'resolved': aggregates['resolved'],
                'reopened': aggregates['reopened'],
                'overdue': aggregates['overdue'],
                'escalated': aggregates['escalated'],
            },
            'priority_distribution': priority_distribution,
            'district_distribution': district_distribution,
            'department_distribution': list(dept_data),
        })
