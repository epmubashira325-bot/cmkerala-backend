import uuid
from django.db import models


class ContactEnquiry(models.Model):
    """
    Public general enquiries and contact messages submitted to the portal.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the contact enquiry."
    )
    name = models.CharField(
        max_length=255,
        help_text="Name of the person making the enquiry."
    )
    email = models.EmailField(
        help_text="Email address of the sender."
    )
    subject = models.CharField(
        max_length=255,
        help_text="Subject or topic of the enquiry."
    )
    message = models.TextField(
        help_text="Detailed message text."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the enquiry was received."
    )

    class Meta:
        db_table = 'contact_enquiries'
        ordering = ['-created_at']
        verbose_name = 'Contact Enquiry'
        verbose_name_plural = 'Contact Enquiries'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.name} - {self.subject} ({self.created_at.strftime('%Y-%m-%d')})"

    def clean(self):
        super().clean()
        if self.name:
            self.name = self.name.strip()
        if self.email:
            self.email = self.email.strip().lower()
        if self.subject:
            self.subject = self.subject.strip()
