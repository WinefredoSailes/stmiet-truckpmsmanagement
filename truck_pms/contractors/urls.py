from django.urls import path
from . import views

app_name = 'contractors'

urlpatterns = [
    path('', views.contractor_list, name='list'),
    path('<int:pk>/', views.contractor_detail, name='detail'),
    path('create/', views.contractor_create, name='create'),
    path('<int:pk>/edit/', views.contractor_update, name='update'),
]
