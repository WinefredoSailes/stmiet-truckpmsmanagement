from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', RedirectView.as_view(url='accounts/dashboard/', permanent=False)),
    path('trucks/', include('trucks.urls')),
    path('pms/', include('pms.urls')),
    path('joborders/', include('joborders.urls')),
    path('service-log/', include('service_log.urls')),
    path('contractors/', include('contractors.urls')),
    path('kpi/', include('kpi.urls')),
    path('training/', include('training.urls')),
]
