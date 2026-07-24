from django.contrib import admin
from .models import Driver, DriverAssignment, DailyLog


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ['name', 'license_number', 'license_expiry', 'license_status', 'mobile']
    search_fields = ['name', 'license_number']


@admin.register(DriverAssignment)
class DriverAssignmentAdmin(admin.ModelAdmin):
    list_display = ['driver', 'truck', 'assigned_from', 'assigned_until']
    list_filter = ['truck']
    search_fields = ['driver__name', 'truck__unit_number']


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ['truck', 'date', 'mileage_km', 'fuel_liters', 'data_source']
    list_filter = ['data_source', 'date']
    search_fields = ['truck__unit_number']
