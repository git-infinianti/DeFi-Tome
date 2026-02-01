from django.urls import path
from . import views

urlpatterns = [
    path('', views.settings, name='settings'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    path('change-theme/', views.change_theme, name='change_theme'),
    path('api-keys/create/', views.create_api_key, name='create_api_key'),
    path('api-keys/<int:key_id>/revoke/', views.revoke_api_key, name='revoke_api_key'),
    path('api-keys/<int:key_id>/delete/', views.delete_api_key, name='delete_api_key'),
]

