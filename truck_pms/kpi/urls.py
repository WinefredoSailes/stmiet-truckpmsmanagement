from django.urls import path
from . import views

app_name = 'kpi'

urlpatterns = [
    path('mechanic/', views.mechanic_kpi, name='mechanic'),
    path('contractor/', views.contractor_kpi, name='contractor'),
    path('truck-frequency/', views.truck_frequency, name='truck_frequency'),
    path('predictive/', views.predictive_analytics, name='predictive'),
]
