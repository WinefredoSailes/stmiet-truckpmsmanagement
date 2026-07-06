from django.contrib import admin
from .models import JobOrder, JobOrderLineItem, LineItemPart

class LineItemPartInline(admin.TabularInline):
    model = LineItemPart
    extra = 1

class JobOrderLineItemInline(admin.TabularInline):
    model = JobOrderLineItem
    extra = 1
    show_change_link = True

@admin.register(JobOrder)
class JobOrderAdmin(admin.ModelAdmin):
    list_display = [
        'jo_number', 'truck', 'title', 'priority', 'job_type',
        'status', 'assigned_to', 'created_at'
    ]
    list_filter = ['status', 'priority', 'job_type']
    search_fields = ['jo_number', 'title', 'truck__unit_number']
    inlines = [JobOrderLineItemInline]
    readonly_fields = ['jo_number', 'created_at', 'updated_at']

@admin.register(JobOrderLineItem)
class JobOrderLineItemAdmin(admin.ModelAdmin):
    list_display = [
        'job_order', 'description', 'status', 'estimated_hours',
        'actual_hours'
    ]
    list_filter = ['status']
    inlines = [LineItemPartInline]
