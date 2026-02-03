from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import SaveCollectionView, BrowseCollectionsView, PlasmidView

app_name = "plasmids"

urlpatterns = [
    path("save/<str:mode>/<str:job_id>/", SaveCollectionView.as_view(), name="save_collection"),
    path("", BrowseCollectionsView.as_view(), name="collections_list"),
    path("view/<int:plasmid_id>/", PlasmidView.as_view(), name="plasmid_view"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)