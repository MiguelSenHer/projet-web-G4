from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = "browse"

urlpatterns = [
    path("browse/", views.browse_templates, name="browse_templates"),
    path('browse/<int:pk>/download/', views.assembly_download, name='assembly_download'),
    path('browse/<int:pk>/', views.assembly_detail, name='assembly_detail'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)