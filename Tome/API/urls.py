from django.urls import path
from . import views

urlpatterns = [
    path('docs/', views.docs, name='api_docs'),
]
