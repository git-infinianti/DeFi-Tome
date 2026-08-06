from django.urls import path
from . import views

urlpatterns = [
    path('', views.settings, name='settings'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    path('change-theme/', views.change_theme, name='change_theme'),
    path('change-network-mode/', views.change_network_mode, name='change_network_mode'),
    path('change-rpc-endpoint-mode/', views.change_rpc_endpoint_mode, name='change_rpc_endpoint_mode'),
    path('api-keys/create/', views.create_api_key, name='create_api_key'),
    path('api-keys/<int:key_id>/revoke/', views.revoke_api_key, name='revoke_api_key'),
    path('api-keys/<int:key_id>/delete/', views.delete_api_key, name='delete_api_key'),
]

