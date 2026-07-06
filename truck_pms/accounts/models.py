from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        ADMIN = 'ADMIN', 'Admin'
        STAFF = 'STAFF', 'Staff'
        MECHANIC = 'MECHANIC', 'Mechanic'
        CONTRACTOR = 'CONTRACTOR', 'Contractor'
        TRAINEE = 'TRAINEE', 'OJT / Trainee'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    mobile = models.CharField(max_length=20, blank=True)
    specialization = models.CharField(
        max_length=200, blank=True,
        help_text="e.g., Engine, Electrical, Welding, General"
    )
    employee_id = models.CharField(max_length=50, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['username']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
