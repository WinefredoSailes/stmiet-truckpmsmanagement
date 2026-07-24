from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


class Driver(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    age = models.IntegerField(null=True, blank=True)
    license_number = models.CharField(max_length=100, unique=True)
    license_expiry = models.DateField()
    mobile = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.license_number})"

    def license_status(self):
        if not self.license_expiry:
            return 'unknown'
        today = timezone.now().date()
        delta = (self.license_expiry - today).days
        if delta < 0:
            return 'overdue'
        if delta <= 30:
            return 'due_soon'
        return 'ok'


class DriverAssignment(models.Model):
    driver = models.ForeignKey(
        Driver, on_delete=models.CASCADE, related_name='assignments'
    )
    truck = models.ForeignKey(
        'trucks.Truck', on_delete=models.CASCADE, related_name='driver_assignments'
    )
    assigned_from = models.DateField()
    assigned_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_from']
        unique_together = ['driver', 'truck', 'assigned_from']

    def __str__(self):
        until = self.assigned_until or 'present'
        return f"{self.driver.name} -> {self.truck.unit_number} ({self.assigned_from} - {until})"


class DailyLog(models.Model):
    class DataSource(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual Entry'
        CARTRACK = 'CARTRACK', 'Cartrack API'
        BOTH = 'BOTH', 'Both'

    truck = models.ForeignKey(
        'trucks.Truck', on_delete=models.CASCADE, related_name='daily_logs'
    )
    date = models.DateField()
    driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='daily_logs'
    )

    mileage_km = models.IntegerField(
        default=0, help_text="End-of-day odometer reading"
    )
    engine_hours = models.DecimalField(
        max_digits=10, decimal_places=1, default=0,
        help_text="End-of-day engine hours"
    )
    fuel_liters = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Fuel added (liters)"
    )
    idle_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )
    idle_count = models.IntegerField(default=0)
    operating_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )
    distance_traveled_km = models.DecimalField(
        max_digits=10, decimal_places=1, default=0
    )
    max_speed_kmh = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    avg_speed_kmh = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    harsh_braking_count = models.IntegerField(default=0)
    harsh_acceleration_count = models.IntegerField(default=0)
    harsh_turning_count = models.IntegerField(default=0)
    data_source = models.CharField(
        max_length=10, choices=DataSource.choices, default=DataSource.MANUAL
    )
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['truck', 'date']
        ordering = ['-date', 'truck__unit_number']

    def __str__(self):
        return f"{self.truck.unit_number} - {self.date}"

    def fuel_efficiency(self):
        if self.fuel_liters and self.fuel_liters > 0 and self.distance_traveled_km > 0:
            return round(float(self.distance_traveled_km) / float(self.fuel_liters), 2)
        return None

    def utilization_rate(self):
        total = float(self.operating_hours) + float(self.idle_hours)
        if total > 0:
            return round(float(self.operating_hours) / total * 100, 1)
        return None

    def total_harsh_events(self):
        return self.harsh_braking_count + self.harsh_acceleration_count + self.harsh_turning_count

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new or 'mileage_km' in kwargs.get('update_fields', []) or True:
            truck = self.truck
            changed = False
            if self.mileage_km and self.mileage_km != truck.current_mileage_km:
                truck.current_mileage_km = self.mileage_km
                changed = True
            if self.engine_hours and float(self.engine_hours) != float(truck.current_engine_hours):
                truck.current_engine_hours = self.engine_hours
                changed = True
            if changed:
                truck.save(update_fields=['current_mileage_km', 'current_engine_hours'])
