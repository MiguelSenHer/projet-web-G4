from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    UploadTemplateView,
    TemplatePreviewView,
    RunSimulationView,
    DownloadOutputsView,
    SimulatorHomeView,
    SimulationsListView,
    DownloadOutputsByJobView,
    ResumeSimulationView,
    DeleteSimulationView,
)

app_name = "simulator"

urlpatterns = [
    path("", SimulatorHomeView.as_view(), name="home"),
    path("upload/", UploadTemplateView.as_view(), name="upload"),
    path("preview/", TemplatePreviewView.as_view(), name="preview"),
    path("run/", RunSimulationView.as_view(), name="run"),
    path("outputs/download/", DownloadOutputsView.as_view(), name="download_outputs"),
    path("my_simulations/", SimulationsListView.as_view(), name="simulations_list"),
    path("outputs/download/<str:job_id>/", DownloadOutputsByJobView.as_view(), name="download_by_job"),
    path("resume/<str:job_id>/", ResumeSimulationView.as_view(), name="resume_job"),
    path("delete/<str:job_id>/", DeleteSimulationView.as_view(), name="delete_job"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
