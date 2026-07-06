from django import forms
from .models import Truck
from core.forms import BootstrapFormMixin


class TruckForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Truck
        fields = [
            'unit_number', 'plate_number', 'chassis_number',
            'engine_number', 'make', 'model', 'year',
            'tank_capacity_liters', 'fuel_type', 'status',
            'current_mileage_km', 'current_engine_hours', 'notes'
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
