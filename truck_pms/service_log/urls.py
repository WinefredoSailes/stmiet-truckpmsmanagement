from django.urls import path
from . import views

app_name = 'service_log'

urlpatterns = [
    path('truck/<int:truck_pk>/', views.truck_ledger, name='truck_ledger'),
    path('all/', views.full_ledger, name='full_ledger'),
]
