from django.urls import path
from . import views

app_name = 'pms'

urlpatterns = [
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_update, name='template_update'),
    path('schedules/', views.schedule_list, name='schedule_list'),
    path('schedules/csv/', views.schedule_csv, name='schedule_csv'),
    path('schedules/print/', views.schedule_print, name='schedule_print'),
    path('schedules/pdf/', views.schedule_pdf, name='schedule_pdf'),
    path('schedules/<int:pk>/edit/', views.schedule_update, name='schedule_update'),
    path('schedules/<int:pk>/complete/', views.complete_task, name='complete_task'),
    path('sync-truck/<int:truck_pk>/', views.sync_truck, name='sync_truck'),
    path('sync-all/', views.sync_all_trucks, name='sync_all'),
    path('pm-tasks-json/<int:truck_pk>/', views.pm_tasks_json, name='pm_tasks_json'),
]
