from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = "browse"

urlpatterns = [
    path("", views.browse_templates, name="browse_templates"),
    path('<int:pk>/download/', views.assembly_download, name='assembly_download'),
    path('<int:pk>/', views.assembly_details, name='assembly_details'),
    path('<int:pk>/copy/', views.copy_assembly, name='copy_assembly'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)