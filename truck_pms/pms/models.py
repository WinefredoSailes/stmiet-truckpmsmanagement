from django.db import models
from django.utils import timezone
from datetime import timedelta


class TaskCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Task Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class TaskTemplate(models.Model):
    class IntervalType(models.TextChoices):
        MILEAGE = 'MILEAGE', 'Mileage (km)'
        HOURS = 'HOURS', 'Engine Hours'
        CALENDAR = 'CALENDAR', 'Calendar (days)'
        VISUAL = 'VISUAL', 'Visual Inspection'

    category = models.ForeignKey(
        TaskCategory, on_delete=models.CASCADE, related_name='templates'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    interval_type = models.CharField(
        max_length=20, choices=IntervalType.choices,
        default=IntervalType.MILEAGE
    )
    interval_value = models.IntegerField(
        null=True, blank=True,
        help_text="Interval value (km, hours, or days)"
    )
    requires_specialist = models.BooleanField(default=False)
    specialist_trade = models.CharField(
        max_length=100, blank=True,
        help_text="e.g., Electrician, Welder, Machinist"
    )
    estimated_labor_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=1.0
    )

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.category.name} \u2192 {self.name}"


class PMSchedule(models.Model):
    truck = models.ForeignKey(
        'trucks.Truck', on_delete=models.CASCADE,
        related_name='pm_schedules'
    )
    task_template = models.ForeignKey(
        TaskTemplate, on_delete=models.CASCADE,
        related_name='schedules'
    )
    is_active = models.BooleanField(default=True)
    last_completed_at = models.DateTimeField(null=True, blank=True)
    last_mileage_km = models.IntegerField(null=True, blank=True)
    last_engine_hours = models.DecimalField(
        max_digits=10, decimal_places=1, null=True, blank=True
    )

    class Meta:
        unique_together = ['truck', 'task_template']
        ordering = ['truck', 'task_template__category', 'task_template__name']

    def __str__(self):
        return f"{self.truck.unit_number} \u2192 {self.task_template.name}"

    def next_due_mileage(self):
        if (self.last_mileage_km is not None
                and self.task_template.interval_type == 'MILEAGE'
                and self.task_template.interval_value):
            return self.last_mileage_km + self.task_template.interval_value
        return None

    def next_due_hours(self):
        if (self.last_engine_hours is not None
                and self.task_template.interval_type == 'HOURS'
                and self.task_template.interval_value):
            return self.last_engine_hours + self.task_template.interval_value
        return None

    def next_due_date(self):
        if (self.last_completed_at is not None
                and self.task_template.interval_type == 'CALENDAR'
                and self.task_template.interval_value):
            return self.last_completed_at + timedelta(
                days=self.task_template.interval_value
            )
        return None

    def status(self):
        if not self.is_active:
            return 'inactive'
        truck = self.truck
        tt = self.task_template
        if tt.interval_type == 'VISUAL':
            return 'visual'
        if tt.interval_type == 'MILEAGE':
            nxt = self.next_due_mileage()
            if nxt is None:
                return 'no_data'
            if truck.current_mileage_km >= nxt:
                return 'overdue'
            if truck.current_mileage_km >= nxt - (tt.interval_value * 0.1):
                return 'due'
            return 'ok'
        if tt.interval_type == 'HOURS':
            nxt = self.next_due_hours()
            if nxt is None:
                return 'no_data'
            if float(truck.current_engine_hours) >= nxt:
                return 'overdue'
            if float(truck.current_engine_hours) >= nxt - (tt.interval_value * 0.1):
                return 'due'
            return 'ok'
        if tt.interval_type == 'CALENDAR':
            nxt = self.next_due_date()
            if nxt is None:
                return 'no_data'
            if timezone.now() >= nxt:
                return 'overdue'
            if timezone.now() >= nxt - timedelta(days=tt.interval_value * 0.1):
                return 'due'
            return 'ok'
        return 'unknown'
