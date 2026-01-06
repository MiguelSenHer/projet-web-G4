from django.urls import path
from .views import home, assembly


urlpatterns = [
    path("", home, name="home"),
    path("assembly/", assembly, name="assembly"),
]
