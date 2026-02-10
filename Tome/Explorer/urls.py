from django.urls import path
from . import views

urlpatterns = [
    path('', views.explorer, name='explorer'),
    path('block/<int:height>/', views.block_detail, name='block_detail'),
    path('tx/<str:txid>/', views.transaction_detail, name='transaction_detail'),
]
