from django.db import models
from django.utils import timezone


class JobOrder(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        EMERGENCY = 'EMERGENCY', 'Emergency'

    class JobType(models.TextChoices):
        PM = 'PM', 'Preventive Maintenance'
        REPAIR = 'REPAIR', 'Repair'
        INSPECTION = 'INSPECTION', 'Inspection'
        CONTRACTOR = 'CONTRACTOR', 'Contractor Service'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        CLOSED = 'CLOSED', 'Closed'

    jo_number = models.CharField(max_length=20, unique=True, editable=False)
    truck = models.ForeignKey(
        'trucks.Truck', on_delete=models.CASCADE, related_name='job_orders'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )
    job_type = models.CharField(
        max_length=20, choices=JobType.choices, default=JobType.REPAIR
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    assigned_to = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_job_orders'
    )
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_job_orders'
    )
    contractor = models.ForeignKey(
        'contractors.Contractor', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='job_orders'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_mileage_km = models.IntegerField(null=True, blank=True)
    completed_engine_hours = models.DecimalField(
        max_digits=10, decimal_places=1, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.jo_number

    def total_parts_cost(self):
        total = 0
        for item in self.line_items.all():
            total += item.total_parts_cost()
        return total

    def total_labor_hours(self):
        return sum(item.actual_hours or 0 for item in self.line_items.all())

    def save(self, *args, **kwargs):
        if not self.jo_number:
            year = timezone.now().year
            last_jo = JobOrder.objects.filter(
                jo_number__startswith=f'JO-{year}-'
            ).order_by('jo_number').last()
            if last_jo:
                last_num = int(last_jo.jo_number.rsplit('-', 1)[-1])
                self.jo_number = f'JO-{year}-{last_num + 1:04d}'
            else:
                self.jo_number = f'JO-{year}-0001'
        super().save(*args, **kwargs)


class JobOrderLineItem(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        DONE = 'DONE', 'Done'

    job_order = models.ForeignKey(
        JobOrder, on_delete=models.CASCADE, related_name='line_items'
    )
    task_template = models.ForeignKey(
        'pms.TaskTemplate', on_delete=models.SET_NULL,
        null=True, blank=True
    )
    category = models.ForeignKey(
        'pms.TaskCategory', on_delete=models.SET_NULL,
        null=True, blank=True
    )
    description = models.CharField(max_length=300)
    estimated_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    actual_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['category', 'id']

    def __str__(self):
        return f"{self.job_order.jo_number} - {self.description[:50]}"

    def total_parts_cost(self):
        return sum(p.total_cost() for p in self.parts.all())


class LineItemPart(models.Model):
    line_item = models.ForeignKey(
        JobOrderLineItem, on_delete=models.CASCADE, related_name='parts'
    )
    part_name = models.CharField(max_length=200)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1
    )
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    def total_cost(self):
        return self.quantity * self.unit_cost

    def __str__(self):
        return f"{self.part_name} x{self.quantity}"
