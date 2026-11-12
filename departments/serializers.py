from rest_framework import serializers
from .models import Department
from accounts.models import User


class DepartmentSerializer(serializers.ModelSerializer):
    """
    Standard Department serializer.
    """
    officer_count = serializers.IntegerField(read_only=True)
    active_grievance_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = (
            'id',
            'name',
            'code',
            'description',
            'is_active',
            'officer_count',
            'active_grievance_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_code(self, value):
        norm_code = value.strip().upper()
        # Ensure code uniqueness on create/update
        qs = Department.objects.filter(code__iexact=norm_code)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Department code already exists.")
        return norm_code

    def validate_name(self, value):
        return value.strip()

