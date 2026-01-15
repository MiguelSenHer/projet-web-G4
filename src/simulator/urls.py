from django.urls import path
from .views import UploadTemplateView, TemplatePreviewView

app_name = "simulator"

urlpatterns = [
    path("upload/", UploadTemplateView.as_view(), name="upload"),
    path("preview/<int:pk>/", TemplatePreviewView.as_view(), name="preview"),
]
