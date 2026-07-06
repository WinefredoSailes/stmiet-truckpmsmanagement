from django.db import models
from django.core.validators import MinValueValidator


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
    # ── Certificate of Registration fields ──
    mv_file_no = models.CharField(
        max_length=50, blank=True, verbose_name='MV File No'
    )
    denomination = models.CharField(
        max_length=50, blank=True,
        help_text="e.g. TRUCK, TRACTOR HEAD"
    )
    piston_displacement_cc = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Piston Displacement (cc)'
    )
    no_of_cylinders = models.IntegerField(
        null=True, blank=True, verbose_name='No. of Cylinders'
    )
    series = models.CharField(max_length=100, blank=True)
    body_type = models.CharField(
        max_length=100, blank=True,
        help_text="e.g. TANKER, WING VAN, DUMP TRUCK"
    )
    body_no = models.CharField(
        max_length=50, blank=True, verbose_name='Body No.'
    )
    gross_weight_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Gross Weight (kg)'
    )
    net_weight_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Net Weight (kg)'
    )
    shipping_weight_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Shipping Weight (kg)'
    )
    net_capacity_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Net Capacity (kg)'
    )
    or_number = models.CharField(
        max_length=50, blank=True, verbose_name='OR Number'
    )
    or_expiry = models.DateField(
        null=True, blank=True, verbose_name='OR Expiry/Validity'
    )
    cr_number = models.CharField(
        max_length=50, blank=True, verbose_name='CR Number'
    )
    field_office_code = models.CharField(max_length=50, blank=True)
    lto_registered_address = models.TextField(
        blank=True, verbose_name='LTO Registered Address'
    )
    # ── End of CR fields ──
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['unit_number']

    def __str__(self):
        return f"{self.unit_number} - {self.plate_number}"
