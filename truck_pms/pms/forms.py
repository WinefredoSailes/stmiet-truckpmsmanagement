from django import forms
from .models import TaskCategory, TaskTemplate, PMSchedule
from core.forms import BootstrapFormMixin


class TaskCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaskCategory
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class TaskTemplateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaskTemplate
        fields = [
            'category', 'name', 'description', 'interval_type',
            'interval_value', 'requires_specialist', 'specialist_trade',
            'estimated_labor_hours'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class PMScheduleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PMSchedule
        fields = [
            'truck', 'task_template', 'is_active',
            'last_completed_at', 'last_mileage_km', 'last_engine_hours'
        ]
        widgets = {
            'last_completed_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
        }
