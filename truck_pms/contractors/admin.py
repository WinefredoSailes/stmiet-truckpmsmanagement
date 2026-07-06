from django.contrib import admin
from .models import Contractor

@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = [
        'company_name', 'contact_person', 'mobile', 'email', 'is_active'
    ]
    list_filter = ['is_active']
    search_fields = ['company_name', 'contact_person']
