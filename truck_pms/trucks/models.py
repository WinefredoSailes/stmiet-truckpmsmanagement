from django.db import models


class Truck(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        DOWN = 'DOWN', 'Down'
        RETIRED = 'RETIRED', 'Retired'

    unit_number = models.CharField(max_length=50, unique=True)
    plate_number = models.CharField(max_length=50, unique=True)
    chassis_number = models.CharField(max_length=100, blank=True)
    engine_number = models.CharField(max_length=100, blank=True)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.IntegerField()
    tank_capacity_liters = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    fuel_type = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    current_mileage_km = models.IntegerField(
        default=0, help_text="Current odometer reading in km"
    )
    current_engine_hours = models.DecimalField(
        max_digits=10, decimal_places=1, default=0,
        help_text="Current engine hours"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['unit_number']

    def __str__(self):
        return f"{self.unit_number} - {self.plate_number}"
