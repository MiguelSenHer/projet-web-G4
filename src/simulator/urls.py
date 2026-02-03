from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from .views import (
    UploadTemplateView,
    TemplatePreviewView,
    RunSimulationView,
    DownloadResultsView,
    SimulatorHomeView,
    SimulationsListView,
    DownloadOutputsByJobView,
    ResumeSimulationView,
    DeleteSimulationView,
    PlasmidView,
)
app_name = "simulator"

urlpatterns = [
    path("", SimulatorHomeView.as_view(), name="home"),
    path("upload/", UploadTemplateView.as_view(), name="upload"),
    path("preview/", TemplatePreviewView.as_view(), name="preview"),
    path("run/", RunSimulationView.as_view(), name="run"),
    path("outputs/download/", DownloadResultsView.as_view(), name="download_results"),
    path("simulations/", SimulationsListView.as_view(), name="simulations_list"),
    path("outputs/download/<str:job_id>/", DownloadOutputsByJobView.as_view(), name="download_by_job"),
    path("resume/<str:job_id>/", ResumeSimulationView.as_view(), name="resume_job"),
    path("delete/<str:job_id>/", DeleteSimulationView.as_view(), name="delete_job"),
    path("plasmid/<str:job_id>/<str:mode>/<str:filename>/", PlasmidView.as_view(), name="plasmid_view"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
