"""Users and library member profiles.

A single ``User`` table carries authentication for every role. ``PatronProfile``
holds the library-specific membership data (member code, class, status) and
exists only for students and teachers.
"""

from datetime import date

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Create users with an email address instead of a username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)  # None leaves an unusable password (invite flow)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("must_change_password", False)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"
        LIBRARIAN = "librarian", "Librarian"
        ADMIN = "admin", "Administrator"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    must_change_password = models.BooleanField(
        default=True,
        help_text="Set for invited accounts; the client forces a password change on first login.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Unset to block sign-in without deleting the member's history.",
    )
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name", "email"]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_patron(self) -> bool:
        """Students and teachers borrow; librarians and admins manage."""
        return self.role in {self.Role.STUDENT, self.Role.TEACHER}

    @property
    def is_library_staff(self) -> bool:
        return self.role in {self.Role.LIBRARIAN, self.Role.ADMIN} or self.is_superuser


class PatronProfile(models.Model):
    """Library membership record for a student or teacher."""

    class Status(models.TextChoices):
        GOOD_STANDING = "good_standing", "Good standing"
        SUSPENDED = "suspended", "Suspended"
        GRADUATED = "graduated", "Graduated"
        INACTIVE = "inactive", "Inactive"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="patron_profile")
    member_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Printed on the library card; auto-generated as STU-00001 / TCH-00001.",
    )
    class_section = models.CharField(max_length=60, blank=True)
    department = models.CharField(max_length=80, blank=True)
    joined_on = models.DateField(default=date.today)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GOOD_STANDING)

    class Meta:
        ordering = ["member_code"]
        verbose_name = "member profile"

    def __str__(self) -> str:
        return f"{self.member_code} — {self.user.full_name}"
