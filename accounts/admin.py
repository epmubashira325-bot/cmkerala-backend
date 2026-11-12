from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Django Admin interface for custom User model.
    """
    model = User

    list_display = (
        'email',
        'full_name',
        'role',
        'department',
        'mobile_number',
        'is_active',
        'is_staff',
        'created_at',
    )
    list_filter = ('role', 'is_active', 'is_staff', 'department')
    search_fields = ('email', 'full_name', 'mobile_number')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_login')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'mobile_number')}),
        ('Role & Affiliation', {'fields': ('role', 'department')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Audit Metadata', {'fields': ('id', 'last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'role', 'department', 'mobile_number', 'password1', 'password2'),
        }),
    )
