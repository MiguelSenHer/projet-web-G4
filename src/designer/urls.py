from django.urls import path
from . import views

app_name = "designer"

urlpatterns = [
    path("", views.design_home, name="design_home"),
    path("properties/", views.designer_properties, name="designer_properties"),
    path("input-parts/<int:pk>/", views.designer_input_parts, name="designer_input_parts"),
    path("summary/<int:pk>/", views.designer_summary, name="designer_summary"),
]
