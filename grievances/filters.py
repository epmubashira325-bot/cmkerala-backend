import django_filters
from .models import Grievance


class GrievanceFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Grievance.Status.choices)
    priority = django_filters.ChoiceFilter(choices=Grievance.Priority.choices)
    district = django_filters.ChoiceFilter(choices=Grievance.District.choices)
    department = django_filters.UUIDFilter(field_name='assigned_department__id')
    officer = django_filters.UUIDFilter(field_name='assigned_officer__id')
    is_escalated = django_filters.BooleanFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Grievance
        fields = [
            'status',
            'priority',
            'district',
            'department',
            'officer',
            'is_escalated',
            'created_after',
            'created_before',
        ]

