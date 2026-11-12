import os
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


def grievance_attachment_upload_path(instance, filename):
    """
    Generate secure and isolated path for grievance attachments.
    Files are stored under: media/grievances/<grievance_id>/<uuid>_<filename>
    """
    ext = os.path.splitext(filename)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    grievance_id = str(instance.grievance_id) if instance.grievance_id else 'unassigned'
    return os.path.join('grievances', grievance_id, unique_filename)


def atr_attachment_upload_path(instance, filename):
    """
    Generate secure path for Action Taken Report (ATR) documents.
    """
    ext = os.path.splitext(filename)[1].lower()
    unique_filename = f"atr_{uuid.uuid4().hex}{ext}"
    grievance_id = str(instance.grievance_id) if instance.grievance_id else 'unassigned'
    return os.path.join('grievances', grievance_id, 'atr', unique_filename)


class Grievance(models.Model):
    """
    Core Grievance Model for Chief Minister's Public Grievance Redressal Portal.
    """
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'

    class Status(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'Submitted'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        REOPENED = 'REOPENED', 'Reopened'

    class District(models.TextChoices):
        ALAPPUZHA = 'ALAPPUZHA', 'Alappuzha'
        ERNAKULAM = 'ERNAKULAM', 'Ernakulam'
        IDUKKI = 'IDUKKI', 'Idukki'
        KANNUR = 'KANNUR', 'Kannur'
        KASARAGOD = 'KASARAGOD', 'Kasaragod'
        KOLLAM = 'KOLLAM', 'Kollam'
        KOTTAYAM = 'KOTTAYAM', 'Kottayam'
        KOZHIKODE = 'KOZHIKODE', 'Kozhikode'
        MALAPPURAM = 'MALAPPURAM', 'Malappuram'
        PALAKKAD = 'PALAKKAD', 'Palakkad'
        PATHANAMTHITTA = 'PATHANAMTHITTA', 'Pathanamthitta'
        THIRUVANANTHAPURAM = 'THIRUVANANTHAPURAM', 'Thiruvananthapuram'
        THRISSUR = 'THRISSUR', 'Thrissur'
        WAYANAD = 'WAYANAD', 'Wayanad'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID primary key."
    )
    reference_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Human-readable unique tracking reference (e.g. CMK-2026-XXXXXX)."
    )
    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='filed_grievances',
        help_text="Citizen who filed the grievance."
    )
    district = models.CharField(
        max_length=50,
        choices=District.choices,
        db_index=True,
        help_text="Kerala District where grievance originated."
    )
    category = models.CharField(
        max_length=120,
        db_index=True,
        help_text="Grievance classification (e.g., Public Infrastructure, Healthcare, Revenue, Welfare)."
    )
    subject = models.CharField(
        max_length=255,
        help_text="Brief subject of the grievance."
    )
    description = models.TextField(
        help_text="Detailed description of the citizen's complaint."
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
        help_text="Priority level assessed manually or via AI triage."
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True,
        help_text="Current life-cycle status of the grievance."
    )
    assigned_department = models.ForeignKey(
        'departments.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_grievances',
        help_text="Department currently responsible for resolving this grievance."
    )
    assigned_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='officer_grievances',
        help_text="Officer currently designated to investigate and handle this grievance."
    )
    ai_suggestions = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON payload containing AI department recommendation, priority score, and extracted summary."
    )
    ai_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="AI provider, model version, timestamp and inference token counts."
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Target resolution deadline according to citizen charter SLA."
    )
    is_escalated = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag indicating overdue escalation to CMO supervisor."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp of submission."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of latest modification."
    )

    class Meta:
        db_table = 'grievances'
        ordering = ['-created_at']
        verbose_name = 'Grievance'
        verbose_name_plural = 'Grievances'
        indexes = [
            models.Index(fields=['reference_number']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['assigned_department', 'status']),
            models.Index(fields=['assigned_officer', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_escalated']),
        ]

    def __str__(self):
        return f"{self.reference_number} - {self.subject[:50]}"

    def clean(self):
        super().clean()
        if self.subject:
            self.subject = self.subject.strip()
        if self.category:
            self.category = self.category.strip()

        # Validate that citizen has CITIZEN role
        if self.citizen_id and hasattr(self.citizen, 'role') and self.citizen.role != 'CITIZEN':
            raise ValidationError({
                'citizen': 'Only users with the CITIZEN role can file grievances.'
            })

        # Validate assigned officer belongs to assigned department
        if self.assigned_officer and self.assigned_department:
            if self.assigned_officer.department_id != self.assigned_department_id:
                raise ValidationError({
                    'assigned_officer': (
                        f"Assigned officer '{self.assigned_officer.full_name}' belongs to "
                        f"'{self.assigned_officer.department}', not '{self.assigned_department}'."
                    )
                })

    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Generate reference number if not set: CMK-YYYYMMDD-8CHARHEX
            import datetime
            now_str = datetime.datetime.now().strftime('%Y%m%d')
            self.reference_number = f"CMK-{now_str}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class GrievanceHistory(models.Model):
    """
    Audit trail recording every state transition for full accountability.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this audit log."
    )
    grievance = models.ForeignKey(
        Grievance,
        on_delete=models.CASCADE,
        related_name='history_logs',
        help_text="Associated grievance."
    )
    previous_status = models.CharField(
        max_length=20,
        choices=Grievance.Status.choices,
        help_text="Grievance status prior to transition."
    )
    new_status = models.CharField(
        max_length=20,
        choices=Grievance.Status.choices,
        help_text="Grievance status after transition."
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='grievance_status_changes',
        help_text="User (Citizen, Officer, or CMO Admin) who initiated this transition."
    )
    remarks = models.TextField(
        blank=True,
        default='',
        help_text="Notes explaining reasons for the status transition."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the transition occurred."
    )

    class Meta:
        db_table = 'grievance_history'
        ordering = ['-created_at']
        verbose_name = 'Grievance History'
        verbose_name_plural = 'Grievance Histories'
        indexes = [
            models.Index(fields=['grievance', 'created_at']),
        ]

    def __str__(self):
        return f"{self.grievance.reference_number}: {self.previous_status} -> {self.new_status} by {self.changed_by}"


class DepartmentAssignment(models.Model):
    """
    Preserves historical and current assignments of grievances to departments and officers.
    Does not overwrite past assignment records.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique assignment identifier."
    )
    grievance = models.ForeignKey(
        Grievance,
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text="Target grievance."
    )
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.PROTECT,
        related_name='grievance_assignments',
        help_text="Department to which grievance is assigned."
    )
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        help_text="Individual officer assigned to investigate."
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='delegated_assignments',
        help_text="User (CMO Admin or Department Nodal Officer) who dispatched the assignment."
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Date and time when assignment was initiated."
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="SLA resolution deadline specified during assignment."
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Indicates if this assignment is currently active."
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when assignment concluded or was reassigned."
    )

    class Meta:
        db_table = 'department_assignments'
        ordering = ['-assigned_at']
        verbose_name = 'Department Assignment'
        verbose_name_plural = 'Department Assignments'
        indexes = [
            models.Index(fields=['grievance', 'is_active']),
            models.Index(fields=['department', 'is_active']),
            models.Index(fields=['officer', 'is_active']),
        ]

    def __str__(self):
        officer_name = self.officer.full_name if self.officer else 'Unallocated'
        return f"{self.grievance.reference_number} -> {self.department.code} ({officer_name})"

    def clean(self):
        super().clean()
        if self.officer and self.department:
            if self.officer.department_id != self.department_id:
                raise ValidationError({
                    'officer': f"Officer '{self.officer.full_name}' does not belong to department '{self.department.name}'."
                })


class GrievanceAttachment(models.Model):
    """
    Supporting documents, photos, and evidence uploaded for a grievance.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique attachment identifier."
    )
    grievance = models.ForeignKey(
        Grievance,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Grievance this attachment supports."
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_attachments',
        help_text="User who uploaded this file."
    )
    file = models.FileField(
        upload_to=grievance_attachment_upload_path,
        help_text="Private attachment file."
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename as uploaded by client."
    )
    file_type = models.CharField(
        max_length=100,
        help_text="MIME type or file extension (e.g. application/pdf, image/jpeg)."
    )
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when upload was completed."
    )

    class Meta:
        db_table = 'grievance_attachments'
        ordering = ['-created_at']
        verbose_name = 'Grievance Attachment'
        verbose_name_plural = 'Grievance Attachments'
        indexes = [
            models.Index(fields=['grievance', 'created_at']),
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.grievance.reference_number})"


class ActionTakenReport(models.Model):
    """
    Action Taken Report (ATR) filed by assigned Department Officers.
    Requires CMO review and approval before grievance closure.
    """
    class ReviewStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique ATR report identifier."
    )
    grievance = models.ForeignKey(
        Grievance,
        on_delete=models.CASCADE,
        related_name='action_reports',
        help_text="Grievance investigated."
    )
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_action_reports',
        help_text="Officer who executed the investigation and filed the report."
    )
    investigation_description = models.TextField(
        help_text="Detailed field findings and verification details."
    )
    resolution_details = models.TextField(
        help_text="Action implemented or corrective measures taken."
    )
    report_attachment = models.FileField(
        upload_to=atr_attachment_upload_path,
        null=True,
        blank=True,
        help_text="Optional signed report PDF or photographic evidence of work done."
    )
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
        help_text="Status of CMO administrative review."
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_action_reports',
        help_text="CMO Admin who approved or rejected the report."
    )
    review_remarks = models.TextField(
        blank=True,
        default='',
        help_text="Observations or feedback provided during review."
    )
    submitted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Submission timestamp."
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of review decision."
    )

    class Meta:
        db_table = 'action_taken_reports'
        ordering = ['-submitted_at']
        verbose_name = 'Action Taken Report'
        verbose_name_plural = 'Action Taken Reports'
        indexes = [
            models.Index(fields=['grievance', 'review_status']),
            models.Index(fields=['officer', 'review_status']),
        ]

    def __str__(self):
        return f"ATR: {self.grievance.reference_number} - {self.get_review_status_display()}"

    def clean(self):
        super().clean()
        # Enforce that an officer cannot approve their own report
        if self.reviewed_by and self.officer:
            if self.reviewed_by_id == self.officer_id:
                raise ValidationError({
                    'reviewed_by': 'An officer cannot review or approve their own Action Taken Report.'
                })


class CitizenFeedback(models.Model):
    """
    Citizen rating and feedback recorded after a grievance has been resolved.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique feedback identifier."
    )
    grievance = models.OneToOneField(
        Grievance,
        on_delete=models.CASCADE,
        related_name='feedback',
        help_text="Grievance being rated."
    )
    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_feedbacks',
        help_text="Citizen providing feedback."
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Satisfaction rating between 1 (Very Dissatisfied) and 5 (Very Satisfied)."
    )
    comments = models.TextField(
        blank=True,
        default='',
        help_text="Detailed citizen comments or observations."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when feedback was submitted."
    )

    class Meta:
        db_table = 'citizen_feedbacks'
        ordering = ['-created_at']
        verbose_name = 'Citizen Feedback'
        verbose_name_plural = 'Citizen Feedbacks'
        indexes = [
            models.Index(fields=['rating']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Feedback for {self.grievance.reference_number} - Rating: {self.rating}/5"

    def clean(self):
        super().clean()
        # Only allow feedback after resolution
        if self.grievance_id and hasattr(self.grievance, 'status'):
            if self.grievance.status != Grievance.Status.RESOLVED:
                raise ValidationError({
                    'grievance': (
                        f"Feedback cannot be submitted for grievance '{self.grievance.reference_number}' "
                        f"because its status is '{self.grievance.get_status_display()}'. "
                        "Feedback is only allowed after resolution."
                    )
                })

        # Ensure citizen submitting feedback is the grievance owner
        if self.grievance_id and self.citizen_id:
            if self.grievance.citizen_id != self.citizen_id:
                raise ValidationError({
                    'citizen': 'Only the citizen who filed the grievance can submit feedback.'
                })
