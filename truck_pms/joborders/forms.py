from django import forms
from .models import JobOrder, JobOrderLineItem, LineItemPart
from core.forms import BootstrapFormMixin


class JobOrderForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JobOrder
        fields = [
            'truck', 'title', 'description', 'priority', 'job_type',
            'assigned_to', 'contractor', 'notes'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contractor'].required = False
        self.fields['assigned_to'].required = False

    def clean(self):
        cleaned_data = super().clean()
        job_type = cleaned_data.get('job_type')
        contractor = cleaned_data.get('contractor')
        assigned_to = cleaned_data.get('assigned_to')
        if job_type == 'CONTRACTOR' and not contractor:
            raise forms.ValidationError(
                "Contractor is required for Contractor Service job type."
            )
        if job_type == 'CONTRACTOR' and assigned_to:
            raise forms.ValidationError(
                "Cannot assign to a mechanic for Contractor job type. "
                "Assign to contractor instead."
            )
        return cleaned_data


class JobOrderLineItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JobOrderLineItem
        fields = [
            'task_template', 'category', 'description',
            'estimated_hours', 'notes'
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['task_template'].required = False
        self.fields['category'].required = False


class LineItemPartForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LineItemPart
        fields = ['part_name', 'quantity', 'unit_cost']


class JobOrderStatusForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JobOrder
        fields = ['status', 'completed_mileage_km',
                  'completed_engine_hours', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class LineItemStatusForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JobOrderLineItem
        fields = ['status', 'actual_hours', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
