from rest_framework import serializers


class DashboardOverviewSerializer(serializers.Serializer):
    total_grievances = serializers.IntegerField()
    submitted = serializers.IntegerField()
    under_review = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    resolved = serializers.IntegerField()
    reopened = serializers.IntegerField()
    overdue = serializers.IntegerField()
    escalated = serializers.IntegerField()


class DistrictStatSerializer(serializers.Serializer):
    district = serializers.CharField()
    count = serializers.IntegerField()


class DepartmentStatSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField()
    total_grievances = serializers.IntegerField()
    pending_grievances = serializers.IntegerField()
    resolved_grievances = serializers.IntegerField()


class CMODashboardStatsResponseSerializer(serializers.Serializer):
    overview = DashboardOverviewSerializer()
    priority_distribution = serializers.DictField(child=serializers.IntegerField())
    district_distribution = DistrictStatSerializer(many=True)
    department_distribution = DepartmentStatSerializer(many=True)

