from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import SaveCollectionView, SaveMappingView, BrowseCollectionsView, PlasmidView, MappingView, DownloadCollectionView, DownloadMappingCollectionView

app_name = "plasmids"

urlpatterns = [
    path("", BrowseCollectionsView.as_view(), name="collections_list"),
    path("save/collection/<str:mode>/<str:job_id>/",  SaveCollectionView.as_view(),  name="save_collection"),
    path("save/mapping/<str:job_id>/", SaveMappingView.as_view(),  name="save_mapping"),
    path("view/<int:plasmid_id>/", PlasmidView.as_view(), name="plasmid_view"),
    path("mapping/<int:mapping_id>/", MappingView.as_view(), name="mapping_view"),
    path("download/collection/<int:collection_id>/", DownloadCollectionView, name="download_collection"),
    path("download/mapping_collection/<int:collection_id>/", DownloadMappingCollectionView, name="download_mapping_collection"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)