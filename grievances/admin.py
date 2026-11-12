from django.contrib import admin
from .models import (
    Grievance,
    GrievanceHistory,
    DepartmentAssignment,
    GrievanceAttachment,
    ActionTakenReport,
    CitizenFeedback,
)


class GrievanceHistoryInline(admin.TabularInline):
    model = GrievanceHistory
    extra = 0
    can_delete = False
    readonly_fields = ('previous_status', 'new_status', 'changed_by', 'remarks', 'created_at')


class DepartmentAssignmentInline(admin.TabularInline):
    model = DepartmentAssignment
    extra = 0
    readonly_fields = ('department', 'officer', 'assigned_by', 'assigned_at', 'due_date', 'is_active', 'ended_at')


class GrievanceAttachmentInline(admin.TabularInline):
    model = GrievanceAttachment
    extra = 0
    readonly_fields = ('original_filename', 'file_type', 'file_size', 'uploaded_by', 'created_at')


class ActionTakenReportInline(admin.StackedInline):
    model = ActionTakenReport
    extra = 0
    readonly_fields = ('officer', 'submitted_at', 'reviewed_by', 'reviewed_at')


@admin.register(Grievance)
class GrievanceAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number',
        'subject',
        'district',
        'category',
        'priority',
        'status',
        'assigned_department',
        'assigned_officer',
        'is_escalated',
        'due_date',
        'created_at',
    )
    list_filter = (
        'status',
        'priority',
        'district',
        'is_escalated',
        'assigned_department',
        'created_at',
    )
    search_fields = (
        'reference_number',
        'subject',
        'description',
        'citizen__email',
        'citizen__full_name',
    )
    ordering = ('-created_at',)
    readonly_fields = (
        'id',
        'reference_number',
        'ai_suggestions',
        'ai_metadata',
        'created_at',
        'updated_at',
    )
    inlines = [
        GrievanceHistoryInline,
        DepartmentAssignmentInline,
        GrievanceAttachmentInline,
        ActionTakenReportInline,
    ]

    fieldsets = (
        ('Overview', {
            'fields': ('id', 'reference_number', 'citizen', 'status', 'priority', 'is_escalated', 'due_date')
        }),
        ('Details', {
            'fields': ('district', 'category', 'subject', 'description')
        }),
        ('Department Assignment', {
            'fields': ('assigned_department', 'assigned_officer')
        }),
        ('AI Triage & Classification', {
            'classes': ('collapse',),
            'fields': ('ai_suggestions', 'ai_metadata')
        }),
        ('Audit Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(GrievanceHistory)
class GrievanceHistoryAdmin(admin.ModelAdmin):
    list_display = ('grievance', 'previous_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('previous_status', 'new_status', 'created_at')
    search_fields = ('grievance__reference_number', 'changed_by__email', 'remarks')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'grievance', 'previous_status', 'new_status', 'changed_by', 'remarks', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(DepartmentAssignment)
class DepartmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('grievance', 'department', 'officer', 'assigned_by', 'is_active', 'assigned_at', 'due_date')
    list_filter = ('is_active', 'department', 'assigned_at')
    search_fields = ('grievance__reference_number', 'department__name', 'officer__email')
    ordering = ('-assigned_at',)
    readonly_fields = ('id', 'assigned_at')


@admin.register(GrievanceAttachment)
class GrievanceAttachmentAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'grievance', 'file_type', 'file_size', 'uploaded_by', 'created_at')
    list_filter = ('file_type', 'created_at')
    search_fields = ('original_filename', 'grievance__reference_number', 'uploaded_by__email')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at')


@admin.register(ActionTakenReport)
class ActionTakenReportAdmin(admin.ModelAdmin):
    list_display = (
        'grievance',
        'officer',
        'review_status',
        'reviewed_by',
        'submitted_at',
        'reviewed_at',
    )
    list_filter = ('review_status', 'submitted_at', 'reviewed_at')
    search_fields = ('grievance__reference_number', 'officer__email', 'investigation_description')
    ordering = ('-submitted_at',)
    readonly_fields = ('id', 'submitted_at')


@admin.register(CitizenFeedback)
class CitizenFeedbackAdmin(admin.ModelAdmin):
    list_display = ('grievance', 'citizen', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('grievance__reference_number', 'citizen__email', 'comments')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at')
