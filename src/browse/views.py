from pathlib import Path

import pandas as pd
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .models import Assembly
import os


# View to browse templates
def browse_templates(request):
    assemblies = Assembly.objects.prefetch_related("inputparts_set")
    return render(request, "browse/browse.html", {"assemblies": assemblies, "active_page": "browse"})


# View to download the .xlsx associated with a template 
def assembly_download(request, pk):
    assembly = get_object_or_404(Assembly, pk=pk)
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


# View to check details of an assembly
def assembly_details(request, pk):
    assembly = get_object_or_404(Assembly, id=pk)
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
