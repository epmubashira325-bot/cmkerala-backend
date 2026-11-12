from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import User
from departments.models import Department


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Public representation of user profile across the system.
    """
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'full_name',
            'mobile_number',
            'role',
            'department',
            'department_name',
            'department_code',
            'is_active',
            'created_at',
        )
        read_only_fields = fields


class CitizenRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for citizen self-registration.
    Strictly forces role to CITIZEN and ignores any submitted role or department.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = (
            'email',
            'full_name',
            'mobile_number',
            'password',
            'password_confirm',
        )

    def validate_email(self, value):
        norm_email = value.strip().lower()
        if User.objects.filter(email__iexact=norm_email).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return norm_email

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        # Always create verified citizen account, ignoring external role injection
        user = User.objects.create_citizen(
            email=validated_data['email'],
            password=password,
            full_name=validated_data['full_name'],
            mobile_number=validated_data.get('mobile_number', '')
        )
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that accepts email and password and returns enriched user payload.
    """
    username_field = 'email'

    def validate(self, attrs):
        # Normalize email before authentication
        if 'email' in attrs:
            attrs['email'] = attrs['email'].strip().lower()
        data = super().validate(attrs)
        data['user'] = UserPublicSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    """
    Serializer for invalidating refresh token.
    """
    refresh = serializers.CharField(required=True)

