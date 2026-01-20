from pathlib import Path

import pandas as pd
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .models import Assembly


# View to browse templates
def browse_templates(request):
    assemblies = Assembly.objects.prefetch_related("inputparts_set")
    return render(request, "browse/browse.html", {"assemblies": assemblies, "active_page": "browse"})


# View to download the .xlsx associated with a template 



# View to check details of an assembly
def assembly_detail(request, pk):
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
