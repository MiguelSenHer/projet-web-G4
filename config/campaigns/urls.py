from django.urls import path
from . import views

urlpatterns = [
    path("simulator/", views.simulator_home, name="simulator_home"),
    path("simulator/upload/", views.upload_template, name="upload_template"),
    path("simulator/upload/next/", views.upload_template_next, name="upload_template_next"),
    path("simulator/browse/", views.browse_templates, name="browse_templates"),
    path(
    'simulator/browse/<int:pk>/download/', views.assembly_download, name='assembly_download'),
    path('simulator/browse/<int:pk>/', views.assembly_detail, name='assembly_detail'),
]
