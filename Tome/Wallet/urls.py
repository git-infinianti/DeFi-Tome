from django.urls import path
from . import views

urlpatterns = [
    path('portfolio/', views.portfolio, name='portfolio'),
    path('portfolio/backup/', views.backup_wallet, name='backup_wallet'),
    path('portfolio/transactions/', views.wallet_transactions, name='wallet_transactions'),
    path('portfolio/send/', views.send_funds, name='send_funds'),
    path('portfolio/receive/', views.recieve_funds, name='recieve_funds'),
    path('portfolio/sync-balance/', views.sync_balance, name='sync_balance'),
    path('portfolio/validate-address/', views.validate_address, name='validate_address'),
    path('portfolio/address-qr/', views.address_qr, name='address_qr'),
]
