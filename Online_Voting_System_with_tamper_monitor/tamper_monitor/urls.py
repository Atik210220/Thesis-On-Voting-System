from django.urls import path
from . import views

urlpatterns = [
    path('alerts/count-unacked/', views.unacked_count, name='tamper_unacked_count'),
]
