from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import UploadTemplateView, TemplatePreviewView, RunSimulationView, DownloadOutputsView

app_name = "simulator"

urlpatterns = [
    path("upload/", UploadTemplateView.as_view(), name="upload"),
    path("preview/", TemplatePreviewView.as_view(), name="preview"),
    path("run/", RunSimulationView.as_view(), name="run"),
    path("outputs/download/", DownloadOutputsView.as_view(), name="download_outputs"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
