from pathlib import Path

import pandas as pd
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.db.models import Q
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.shortcuts import redirect


from browse.models import Assembly
import os

# View to browse templates with access control
def browse_templates(request):
    view_filter = request.GET.get('view', 'all')
    if not request.user.is_authenticated:
        qs = Assembly.objects.filter(is_public=True)
    else:
        qs = Assembly.objects.filter(Q(is_public=True) | Q(owner=request.user))
        if view_filter == 'public':
            qs = qs.filter(is_public=True)
        elif view_filter == 'private':
            qs = qs.filter(is_public=False, owner=request.user)
    assemblies = qs.prefetch_related("inputparts_set").distinct()
    return render(request, "browse/browse.html", {
        "assemblies": assemblies, 
        "active_page": "browse",
        "current_filter": view_filter
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

@login_required
def copy_assembly(request, pk):
    source = get_object_or_404(Assembly, Q(pk=pk) & (Q(is_public=True) | Q(owner=request.user)))
    with transaction.atomic():
        new_assembly = Assembly.objects.get(pk=source.pk)
        new_assembly.pk = None  
        new_assembly.id = None
        new_assembly.name = f"Copy of {source.name}"
        new_assembly.owner = request.user
        new_assembly.is_public = False 
        new_assembly.creation_date = timezone.now()
        new_assembly.file = None 
        new_assembly.save()
        for part in source.inputparts_set.all():
            allowed_types = part.allowed_types.all() 
            part.pk = None
            part.id = None
            part.assembly = new_assembly
            part.save()
            part.allowed_types.set(allowed_types) 
    return redirect("designer:designer_properties_edit", pk=new_assembly.pk)

@login_required
def delete_assembly(request, pk):
    assembly = get_object_or_404(Assembly, pk=pk, owner=request.user, is_public=False)
    if request.method == "POST":
        assembly.delete()
        return redirect('browse:browse_templates')
    return redirect('browse:browse_templates')
