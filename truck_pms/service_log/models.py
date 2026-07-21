from django.db import models
from django.utils import timezone


class ServiceLogEntry(models.Model):
    job_order = models.ForeignKey(
        'joborders.JobOrder', on_delete=models.CASCADE,
        null=True, blank=True, related_name='log_entries'
    )
    line_item = models.ForeignKey(
        'joborders.JobOrderLineItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='log_entries'
    )
    truck = models.ForeignKey(
        'trucks.Truck', on_delete=models.CASCADE,
        related_name='service_logs'
    )
    action = models.CharField(max_length=100)
    description = models.TextField()
    performed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, related_name='service_log_entries'
    )
    performed_at = models.DateTimeField(default=timezone.now)
    mileage_at = models.IntegerField(null=True, blank=True)
    engine_hours_at = models.DecimalField(
        max_digits=10, decimal_places=1, null=True, blank=True
    )
    labor_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    parts_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ['-performed_at']
        verbose_name_plural = "Service Log Entries"

    def __str__(self):
        return (
            f"{self.performed_at.date()} | "
            f"{self.truck.unit_number} | {self.action}"
        )
