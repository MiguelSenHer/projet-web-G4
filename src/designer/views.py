from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from browse.models import Assembly
from .forms import AssemblyForm, InputPartsFormSet

from designer.utils.xlsx_generator import generate_assembly_xlsx

import logging
logger = logging.getLogger(__name__)

# Session Keys
SESSION_KEYS = [
    "uploaded_template_path",
    "uploaded_template_name",
    "template_is_valid",
    "assembly_preview",
    "genbank_path",
    "genbank_name",
    "ok_genbank",
    "mapping_path",
    "mapping_name",
    "ok_mapping",
    "last_run_id",
]

def design_home(request):
    # Reset session
    for k in SESSION_KEYS:
        request.session.pop(k, None)
    request.session.modified = True

    options = [
        {
            "label": "CREATE",
            "url": "/designer/properties/"
        },
        {
            "label": "BROWSE EXISTING",
            "url": ""},
    ]
    return render(
        request,
        "designer/designer_home.html",
        {"options": options, "active_page": "designer"}
        )

@login_required
def designer_properties(request):
    assembly = None
    if request.method == "POST":
        form = AssemblyForm(request.POST, instance=assembly)
        if form.is_valid():
            assembly = form.save(commit=False)
            assembly.creation_date = timezone.now()
            assembly.save()
            return redirect("designer:designer_input_parts", pk=assembly.pk)
    else:
        form = AssemblyForm()
    return render(request, "designer/designer_properties.html", {"form": form, "assembly":assembly})

@login_required
def designer_input_parts(request, pk):
    assembly = get_object_or_404(Assembly, pk=pk)
    if request.method == "POST":
        formset = InputPartsFormSet(request.POST, instance=assembly)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for obj in instances:
                obj.assembly = assembly
                obj.save()
            formset.save_m2m()
            if not assembly.file:
                xlsx_content = generate_assembly_xlsx(assembly)
                assembly.file.save(
                    f"assembly_{assembly.pk}.xlsx",
                    xlsx_content,
                    save=True
                )   
            return redirect("designer:designer_summary", pk=assembly.pk)
    else:
        formset = InputPartsFormSet(instance=assembly)
    return render(
        request,
        "designer/designer_input_parts.html",
        {"assembly": assembly, "formset": formset}
    )

@login_required   
def designer_summary(request, pk):
    assembly = get_object_or_404(Assembly, id=pk)
    input_parts = assembly.inputparts_set.prefetch_related("allowed_types")
    return render(
        request,
        "designer/designer_summary.html",
        {
            "assembly": assembly,
            "input_parts": input_parts,
        }
    )
