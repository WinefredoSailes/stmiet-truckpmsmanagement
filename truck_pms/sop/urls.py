from django.urls import path
from . import views

app_name = 'sop'

urlpatterns = [
    path('', views.download_page, name='download_page'),
    path('en/', views.view_en, name='view_en'),
    path('tl/', views.view_tl, name='view_tl'),
    path('download/en/', views.download_en, name='download_en'),
    path('download/tl/', views.download_tl, name='download_tl'),
]
