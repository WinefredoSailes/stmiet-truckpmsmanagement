from django.contrib import admin
from .models import Training, Attendance, TaskRating, WeeklyReview, Holiday


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ['ojt', 'supervisor', 'status', 'start_date', 'end_date']
    list_filter = ['status']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['training', 'date', 'time_in', 'time_out']


@admin.register(TaskRating)
class TaskRatingAdmin(admin.ModelAdmin):
    list_display = ['training', 'task_name', 'rating', 'supervisor', 'created_at']


@admin.register(WeeklyReview)
class WeeklyReviewAdmin(admin.ModelAdmin):
    list_display = ['training', 'week_start', 'week_end', 'overall_score', 'status']


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['date', 'name', 'created_by', 'created_at']
    list_filter = ['date']
    search_fields = ['name']
    date_hierarchy = 'date'
