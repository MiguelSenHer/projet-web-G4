from pathlib import Path

import pandas as pd
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.db.models import Q

from browse.models import Assembly
import os

# View to browse templates with access control
def browse_templates(request):
    # Base Queryset
    qs = Assembly.objects.prefetch_related("inputparts_set")
    if not request.user.is_authenticated:
        assemblies = qs.filter(is_public=True)
    else:
        assemblies = qs.filter(Q(is_public=True) | Q(owner=request.user))
    return render(request, "browse/browse.html", {
        "assemblies": assemblies, 
        "active_page": "browse"
    })


# View to download the .xlsx associated with a template with access control
def assembly_download(request, pk):
    assembly = get_object_or_404(Assembly, pk=pk)
    if not assembly.is_public:
        if not request.user.is_authenticated or assembly.owner != request.user:
            raise Http404("You do not have permission to download this file.")
    if not assembly.file:
        raise Http404("No file associated with this assembly")
    file_path = assembly.file.path
    if not os.path.exists(file_path):
        raise Http404("File not found on server")
    return FileResponse(
        open(file_path, "rb"),
        as_attachment=True,
        filename=os.path.basename(file_path)
    )


# View to check details of an assembly with access control
def assembly_details(request, pk):
    assembly = get_object_or_404(Assembly, id=pk)
    if not assembly.is_public:
        if not request.user.is_authenticated or assembly.owner != request.user:
            raise Http404("You do not have permission to view this assembly.")
    input_parts = assembly.inputparts_set.prefetch_related("allowed_types")
    return render(
        request,
        "browse/assembly_details.html",
        {
            "assembly": assembly,
            "input_parts": input_parts,
            "active_page": "browse"
        }
    )
