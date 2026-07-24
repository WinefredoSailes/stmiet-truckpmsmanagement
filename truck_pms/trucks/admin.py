from django.contrib import admin
from .models import Truck

@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = [
        'unit_number', 'plate_number', 'make', 'model', 'year',
        'current_mileage_km', 'status',
        'or_expiry', 'cr_expiry', 'fire_conveyance_expiry',
        'dost_calibration_expiry',
    ]
    list_filter = ['status', 'make']
    search_fields = ['unit_number', 'plate_number', 'chassis_number']
