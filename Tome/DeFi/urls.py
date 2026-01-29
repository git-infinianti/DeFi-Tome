from django.urls import path
from . import views

urlpatterns = [
    path('testnet/', views.testnet_home, name='testnet_home'),
    path('testnet/swap/', views.swap, name='swap'),
    path('testnet/liquidity/', views.liquidity, name='liquidity'),
    path('testnet/transactions/', views.transactions, name='transactions'),
]
