from django.contrib import admin
from .models import ServiceLogEntry, ServiceLogPart


class ServiceLogPartInline(admin.TabularInline):
    model = ServiceLogPart
    extra = 1


@admin.register(ServiceLogEntry)
class ServiceLogEntryAdmin(admin.ModelAdmin):
    list_display = [
        'performed_at', 'truck', 'action', 'performed_by',
        'labor_hours', 'parts_cost'
    ]
    list_filter = ['action', 'truck']
    search_fields = ['truck__unit_number', 'action', 'description']
    readonly_fields = ['performed_at']
    inlines = [ServiceLogPartInline]


@admin.register(ServiceLogPart)
class ServiceLogPartAdmin(admin.ModelAdmin):
    list_display = ['part_name', 'quantity', 'unit_cost', 'service_log']
