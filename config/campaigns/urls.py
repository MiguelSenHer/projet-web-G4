from django.urls import path
from . import views

urlpatterns = [
    path("simulator/", views.simulator_home, name="simulator_home"),
    path("simulator/load/", views.load_template, name="load_template"),
    path("simulator/browse/", views.browse_templates, name="browse_templates"),
]
