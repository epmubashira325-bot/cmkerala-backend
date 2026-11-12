import uuid
from django.db import models


class Department(models.Model):
    """
    Government departments under Government of Kerala
    responsible for resolving citizen grievances.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the department."
    )
    name = models.CharField(
        max_length=200,
        help_text="Official name of the department (e.g., Revenue, Health, Police)."
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique department short code (e.g., REV, HLT, POL)."
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text="Brief overview of department jurisdiction and services."
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this department is active and can receive assignments."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the department record was created."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the department record was last modified."
    )

    class Meta:
        db_table = 'departments'
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()
