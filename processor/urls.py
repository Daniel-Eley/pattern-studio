from django.urls import path
from . import views

urlpatterns = [
    path('bootstrap/', views.bootstrap),
    path('health/', views.health),
    path('datasets/', views.upload),
    path('datasets/<uuid:pk>/', views.detail),
    path('datasets/<uuid:pk>/preview/', views.preview),
    path('datasets/<uuid:pk>/apply/<uuid:operation_id>/', views.apply),
    path('datasets/<uuid:pk>/reset/', views.reset),
    path('datasets/<uuid:pk>/delete/', views.delete),
    path('datasets/<uuid:pk>/download/', views.download),
]
