from django.urls import path
from django.conf import settings
from .views import SaveCollectionView, BrowseCollectionsView, PlasmidView
from django.conf.urls.static import static

urlpatterns = []

app_name = "plasmids"

urlpatterns += [
     path("save/<str:job_id>/", SaveCollectionView.as_view(), name="save_collection"),
     path("", BrowseCollectionsView.as_view(), name="collections_list"),
     path("view/<int:plasmid_id>/", PlasmidView.as_view(), name="plasmid_view"),
     path("view/<str:job_id>/plasmid/<str:filename>/", PlasmidView.as_view(), name="job_plasmid_view"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)