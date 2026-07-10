from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/check-in/', views.attendance_check_in, name='attendance_check_in'),
    path('attendance/check-out/', views.attendance_check_out, name='attendance_check_out'),
    path('ratings/', views.rating_list, name='rating_list'),
    path('ratings/create/', views.rating_create, name='rating_create'),
    path('ratings/<int:pk>/', views.rating_detail, name='rating_detail'),
    path('reviews/', views.review_list, name='review_list'),
    path('reviews/create/', views.review_create, name='review_create'),
    path('reviews/<int:pk>/', views.review_detail, name='review_detail'),
    path('ojt/<int:pk>/', views.ojt_detail, name='ojt_detail'),
    path('ojt/<int:pk>/ratings/', views.ojt_rating_list, name='ojt_rating_list'),
    path('ojt/<int:pk>/reviews/', views.ojt_review_list, name='ojt_review_list'),
    path('assign/', views.assign_training, name='assign'),
    path('holidays/', views.holiday_list, name='holiday_list'),
]
