"""
accounts/models.py

Custom User model + Firm.

- Email-based authentication (no username)
- Role-based access control (RBAC)
- Every user belongs to a Firm (multi-tenancy root)
"""

from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.db import models


class Firm(models.Model):
    """Top-level tenant. All data is scoped to a firm."""

    name = models.CharField(max_length=255)
    lsk_number = models.CharField(max_length=50, unique=True, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        MANAGING_PARTNER = "managing_partner", "Managing Partner"
        PARTNER = "partner", "Partner"
        ASSOCIATE = "associate", "Associate"
        PARALEGAL = "paralegal", "Paralegal"
        SUPPORT = "support", "Support Staff"

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.ASSOCIATE,
    )

    lsk_number = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_managing_partner(self):
        return self.role == self.Role.MANAGING_PARTNER

    @property
    def is_partner_or_above(self):
        return self.role in (
            self.Role.MANAGING_PARTNER,
            self.Role.PARTNER,
        )

    class Meta:
        ordering = ["last_name", "first_name"]
