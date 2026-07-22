import csv
import io
from django import forms
from django.core.exceptions import ValidationError
from .models import Truck
from core.forms import BootstrapFormMixin


class TruckForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Truck
        fields = [
            'unit_number', 'plate_number', 'chassis_number',
            'engine_number', 'make', 'model', 'year',
            'tank_capacity_liters', 'fuel_type', 'status',
            'current_mileage_km', 'current_engine_hours',
            'mv_file_no', 'denomination', 'piston_displacement_cc',
            'no_of_cylinders', 'series', 'body_type', 'body_no',
            'gross_weight_kg', 'net_weight_kg', 'shipping_weight_kg',
            'net_capacity_kg', 'or_number', 'or_expiry', 'cr_number',
            'field_office_code', 'lto_registered_address', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
            'lto_registered_address': forms.Textarea(attrs={'rows': 2}),
            'or_expiry': forms.DateInput(attrs={'type': 'date'}),
        }


IMPORT_FIELDS = [
    'unit_number', 'plate_number', 'chassis_number', 'engine_number',
    'make', 'model', 'year', 'tank_capacity_liters', 'fuel_type',
    'status', 'current_mileage_km', 'current_engine_hours',
    'mv_file_no', 'denomination', 'piston_displacement_cc',
    'no_of_cylinders', 'series', 'body_type', 'body_no',
    'gross_weight_kg', 'net_weight_kg', 'shipping_weight_kg',
    'net_capacity_kg', 'or_number', 'or_expiry', 'cr_number',
    'field_office_code', 'lto_registered_address', 'notes',
]


class TruckImportForm(forms.Form):
    csv_file = forms.FileField(label='CSV File')

    def clean_csv_file(self):
        f = self.cleaned_data['csv_file']
        if not f.name.endswith('.csv'):
            raise ValidationError('Only CSV files are accepted.')
        return f
