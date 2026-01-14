from django.urls import path
from . import views

urlpatterns = [
    path("simulator/", views.simulator_home, name="simulator_home"),
    path("simulator/upload/", views.upload_template, name="upload_template"),
    path("simulator/browse/", views.browse_templates, name="browse_templates"),
    path("simulator/upload/next/", views.upload_template_next, name="upload_template_next"),
    path("simulator/inputs/", views.simulator_inputs, name="simulator_inputs"),
    path("simulator/preview/", views.simulation_preview, name="simulation_preview"),
    path(
    'simulator/browse/<int:pk>/download/', views.assembly_download, name='assembly_download'),
    path('simulator/browse/<int:pk>/', views.assembly_detail, name='assembly_detail'),
    path("simulator/run/", views.simulation_run, name="simulation_run"),
    path("simulator/run/<str:run_id>/download/", views.simulation_run_download, name="simulation_run_download"),
    path("simulator/simulations/", views.simulations_list, name="simulations_list"),
    path("simulator/run/<str:run_id>/resume/", views.resume_run, name="resume_run"),
    path("simulator/run/<str:run_id>/delete/", views.delete_run, name="delete_run"),
]
