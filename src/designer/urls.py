from django.urls import path
from . import views

urlpatterns = [
    path("designer/", views.design_home, name="design_home"),
    path("designer/properties/", views.designer_properties, name="designer_properties"),
    path("designer/input-parts/<int:pk>/", views.designer_input_parts, name="designer_input_parts"),
    path("designer/summary/<int:pk>/", views.designer_summary, name="designer_summary"),
]
