from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Training(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'
        DROPPED = 'DROPPED', 'Dropped'

    ojt = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='training_profile'
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='supervised_trainees'
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ojt.get_full_name() or self.ojt.username} ({self.status})"


class Attendance(models.Model):
    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name='attendances'
    )
    date = models.DateField(auto_now_add=True)
    time_in = models.TimeField(auto_now_add=True)
    time_out = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Attendances'
        ordering = ['-date', '-time_in']

    def __str__(self):
        return f"{self.training.ojt.username} - {self.date}"


class TaskRating(models.Model):
    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name='task_ratings'
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='given_ratings'
    )
    task_template = models.ForeignKey(
        'pms.TaskTemplate', on_delete=models.SET_NULL,
        null=True, blank=True
    )
    task_name = models.CharField(max_length=200, blank=True)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.training.ojt.username} - {self.task_name or self.task_template} - {self.rating}/5"

    def save(self, *args, **kwargs):
        if self.task_template and not self.task_name:
            self.task_name = self.task_template.name
        super().save(*args, **kwargs)


class WeeklyReview(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'

    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name='weekly_reviews'
    )
    week_start = models.DateField()
    week_end = models.DateField()
    overall_score = models.DecimalField(
        max_digits=3, decimal_places=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    supervisor_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_start']
        unique_together = ['training', 'week_start']

    def __str__(self):
        return f"{self.training.ojt.username} - Week of {self.week_start}"
