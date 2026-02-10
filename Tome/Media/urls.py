from django.urls import path
from . import views

urlpatterns = [
    path('', views.media_list, name='media_list'),
    path('upload/', views.media_upload, name='media_upload'),
    path('<int:pk>/edit/', views.media_edit, name='media_edit'),
    path('<int:pk>/delete/', views.media_delete, name='media_delete'),
]
