from django import forms
from .models import Contractor
from core.forms import BootstrapFormMixin


class ContractorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Contractor
        fields = [
            'company_name', 'contact_person', 'mobile', 'email',
            'address', 'skills', 'is_active', 'notes'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'skills': forms.Textarea(attrs={'rows': 3}),
        }
