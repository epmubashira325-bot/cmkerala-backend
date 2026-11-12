import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email).lower()
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.CMO_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

    def create_citizen(self, email, password=None, **extra_fields):
        """Helper to create verified citizen account."""
        extra_fields['role'] = User.Role.CITIZEN
        extra_fields['department'] = None
        return self.create_user(email, password, **extra_fields)


mobile_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Mobile number must be entered in the format: '+919999999999' or up to 15 digits."
)


class User(AbstractUser):
    """
    Custom User Model for CM Kerala Portal.
    Authenticated primarily via Email.
    Supports CITIZEN, CMO_ADMIN, and OFFICER roles.
    """

    class Role(models.TextChoices):
        CITIZEN = 'CITIZEN', 'Citizen'
        CMO_ADMIN = 'CMO_ADMIN', 'CMO Administrator'
        OFFICER = 'OFFICER', 'Department Officer'

    # Disable standard username in favor of email
    username = None

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for the user."
    )
    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="Primary email address used for login."
    )
    full_name = models.CharField(
        max_length=255,
        help_text="Full legal name of the user."
    )
    mobile_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        validators=[mobile_validator],
        help_text="Contact mobile number."
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CITIZEN,
        db_index=True,
        help_text="Role determining user permissions across the portal."
    )
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='officers',
        help_text="Assigned department (applicable only for Department Officers)."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the user account was created."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the user account was last updated."
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email}) - {self.get_role_display()}"

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
        if self.full_name:
            self.full_name = self.full_name.strip()

        # Enforce role-department consistency
        if self.role == self.Role.OFFICER and not self.department:
            # We enforce that officers must belong to a department
            raise ValidationError({
                'department': 'Department Officers must be assigned to an active department.'
            })
        elif self.role in (self.Role.CITIZEN, self.Role.CMO_ADMIN) and self.department is not None:
            raise ValidationError({
                'department': f'{self.get_role_display()} accounts should not be assigned to a specific department.'
            })

    @property
    def is_citizen(self):
        return self.role == self.Role.CITIZEN

    @property
    def is_cmo_admin(self):
        return self.role == self.Role.CMO_ADMIN

    @property
    def is_officer(self):
        return self.role == self.Role.OFFICER
