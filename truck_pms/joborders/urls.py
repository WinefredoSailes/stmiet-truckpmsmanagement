from django.urls import path
from . import views

app_name = 'joborders'

urlpatterns = [
    path('', views.job_order_list, name='list'),
    path('create/', views.job_order_create, name='create'),
    path('<int:pk>/', views.job_order_detail, name='detail'),
    path('<int:pk>/print/', views.job_order_print, name='print'),
    path('<int:pk>/edit/', views.job_order_update, name='update'),
    path('<int:pk>/pdf/', views.job_order_pdf, name='pdf'),
    path('<int:pk>/close/', views.job_order_close, name='close'),
    path('my-assignments/', views.my_assignments, name='my_assignments'),
    path('line-item/<int:pk>/update/', views.update_line_item, name='update_line_item'),
    path('line-item/<int:item_pk>/add-part/', views.add_line_item_part, name='add_line_item_part'),
    path('<int:pk>/add-line-item/', views.job_order_add_line_item, name='add_line_item'),
]
