from django.urls import path
from . import views

urlpatterns = [
    # Documentation
    path('docs/', views.docs, name='api_docs'),
    
    # API Info
    path('v1/info/', views.api_info, name='api_info'),
    
    # Contract Management
    path('v1/contracts/', views.contracts_list, name='contracts_list'),
    path('v1/contracts/<int:contract_id>/', views.contract_detail, name='contract_detail'),
    path('v1/contracts/<int:contract_id>/interact/', views.contract_interact, name='contract_interact'),
    
    # Asset Management
    path('v1/assets/', views.assets_list, name='assets_list'),
    path('v1/assets/<str:asset_name>/', views.asset_detail, name='asset_detail'),
    path('v1/assets/issue/', views.asset_issue, name='asset_issue'),
    path('v1/assets/transfer/', views.asset_transfer, name='asset_transfer'),
    
    # Blockchain Queries
    path('v1/blockchain/info/', views.blockchain_info, name='blockchain_info'),
    path('v1/blockchain/block/<str:block_hash>/', views.block_info, name='block_info'),
    path('v1/blockchain/address/<str:address>/balance/', views.address_balance, name='address_balance'),
    path('v1/blockchain/address/<str:address>/transactions/', views.address_transactions, name='address_transactions'),
    path('v1/blockchain/address/<str:address>/utxos/', views.address_utxos, name='address_utxos'),
    
    # Messaging
    path('v1/messages/send/', views.send_message, name='send_message'),
    path('v1/messages/', views.view_messages, name='view_messages'),
    path('v1/messages/channels/', views.view_channels, name='view_channels'),
]

