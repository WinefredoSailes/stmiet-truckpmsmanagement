from django.urls import path
from . import views

app_name = 'trucks'

urlpatterns = [
    path('', views.truck_list, name='list'),
    path('<int:pk>/', views.truck_detail, name='detail'),
    path('create/', views.truck_create, name='create'),
    path('<int:pk>/edit/', views.truck_update, name='update'),
    path('export-csv/', views.truck_export_csv, name='export_csv'),
    path('import-csv/', views.truck_import_csv, name='import_csv'),
]
