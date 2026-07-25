from django.urls import path
from . import views

app_name = 'fleetops'

urlpatterns = [
    path('logs/', views.daily_log_list, name='daily_log'),
    path('logs/load/', views.daily_log_load, name='daily_log_load'),
    path('dashboard/', views.fleet_performance, name='fleet_performance'),
    path('drivers/', views.driver_list, name='driver_list'),
    path('drivers/create/', views.driver_create, name='driver_create'),
    path('drivers/<int:pk>/', views.driver_scorecard, name='driver_scorecard'),
    path('drivers/<int:pk>/edit/', views.driver_edit, name='driver_edit'),
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/create/', views.assignment_create, name='assignment_create'),
    path('pull-cartrack/', views.pull_cartrack, name='pull_cartrack'),
    path('compliance/', views.compliance_dashboard, name='compliance_dashboard'),
    path('weekly-report/', views.weekly_report, name='weekly_report'),
]
