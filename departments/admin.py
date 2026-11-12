from django.contrib import admin
from .models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        (None, {'fields': ('name', 'code', 'description', 'is_active')}),
        ('Audit Metadata', {'fields': ('id', 'created_at', 'updated_at')}),
    )
