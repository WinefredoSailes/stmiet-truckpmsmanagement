from django.contrib import admin
from .models import TaskCategory, TaskTemplate, PMSchedule

@admin.register(TaskCategory)
class TaskCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']

@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'interval_type', 'interval_value',
        'requires_specialist'
    ]
    list_filter = ['category', 'interval_type', 'requires_specialist']
    search_fields = ['name', 'description']

@admin.register(PMSchedule)
class PMScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'truck', 'task_template', 'is_active',
        'last_completed_at', 'last_mileage_km'
    ]
    list_filter = ['is_active', 'task_template__category']
    search_fields = ['truck__unit_number', 'task_template__name']
