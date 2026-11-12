from rest_framework import generics
from rest_framework.permissions import AllowAny
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema

from .models import Department
from .serializers import DepartmentSerializer
from accounts.permissions import IsCMOAdmin
from accounts.serializers import UserPublicSerializer


class DepartmentListView(generics.ListAPIView):
    """
    Public listing of active government departments.
    """
    serializer_class = DepartmentSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Department.objects.filter(is_active=True).annotate(
            officer_count=Count('officers', filter=Q(officers__is_active=True))
        ).order_by('name')

    @extend_schema(summary="List all active departments")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DepartmentDetailView(generics.RetrieveAPIView):
    """
    Public retrieve view for specific department.
    """
    serializer_class = DepartmentSerializer
    permission_classes = [AllowAny]
    queryset = Department.objects.filter(is_active=True)

    @extend_schema(summary="Get active department details")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CMODepartmentListCreateView(generics.ListCreateAPIView):
    """
    CMO administration endpoint to list all departments (including inactive) and create new ones.
    """
    serializer_class = DepartmentSerializer
    permission_classes = [IsCMOAdmin]

    def get_queryset(self):
        return Department.objects.annotate(
            officer_count=Count('officers', filter=Q(officers__is_active=True)),
            active_grievance_count=Count(
                'assigned_grievances',
                filter=~Q(assigned_grievances__status='RESOLVED')
            )
        ).order_by('name')

    @extend_schema(summary="CMO: List or create department")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CMODepartmentRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """
    CMO administration endpoint to retrieve and modify department details.
    """
    serializer_class = DepartmentSerializer
    permission_classes = [IsCMOAdmin]
    queryset = Department.objects.all()

    @extend_schema(summary="CMO: Retrieve or update department")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class CMODepartmentOfficersListView(generics.ListAPIView):
    """
    CMO administration endpoint to list officers belonging to a specific department.
    Used during grievance assignment to select a valid department officer.
    """
    serializer_class = UserPublicSerializer
    permission_classes = [IsCMOAdmin]
    pagination_class = None

    def get_queryset(self):
        dept_id = self.kwargs.get('pk')
        from accounts.models import User
        return User.objects.filter(
            role=User.Role.OFFICER,
            department_id=dept_id,
            is_active=True
        ).order_by('full_name')

    @extend_schema(summary="CMO: List active officers for a specific department")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

