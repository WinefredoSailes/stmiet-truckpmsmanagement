from django.urls import path
from . import views

app_name = 'sop'

urlpatterns = [
    path('', views.download_page, name='download_page'),
    path('download/en/', views.download_en, name='download_en'),
    path('download/tl/', views.download_tl, name='download_tl'),
]
