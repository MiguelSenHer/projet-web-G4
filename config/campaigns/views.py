from django.shortcuts import render
from django.conf import settings
from pathlib import Path
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from .models import Assembly

def simulator_home(request):
    options = [
        {"label": "LOAD YOUR PLASMID ASSEMBLY TEMPLATE", "url": "/campaigns/simulator/load/"},
        {"label": "BROWSE PLASMID ASSEMBLY TEMPLATE", "url": "/campaigns/simulator/browse/"},
    ]
    return render(request, "campaigns/template.html", {"options": options})

def load_template(request):
    uploaded_name = None
    error = None

    if request.method == "POST" and request.FILES.get("template_file"):
        f = request.FILES["template_file"]

        # optionnel mais utile : on force le .xlsx
        if not f.name.lower().endswith(".xlsx"):
            error = "Only .xlsx files are allowed."
        else:
            out_dir = Path(settings.MEDIA_ROOT) / "templates"
            out_dir.mkdir(parents=True, exist_ok=True)
            dest = out_dir / f.name

            with open(dest, "wb") as w:
                for chunk in f.chunks():
                    w.write(chunk)

            uploaded_name = f.name

    return render(request, "campaigns/load.html", {"uploaded_name": uploaded_name, "error": error})


def browse_templates(request):
    assemblies = Assembly.objects.prefetch_related('inputparts_set')
    return render(
        request,
        'campaigns/browse.html',
        {'assemblies': assemblies}
    )


def assembly_download(request, pk):
    assembly = get_object_or_404(Assembly, pk=pk)
    if not assembly.file:
        raise Http404("No file associated with this assembly")
    response = FileResponse(
        assembly.file.open('rb'),
        as_attachment=True,
        filename=assembly.file.name.split('/')[-1]
    )
    return response

def assembly_detail(request, pk):
    return render(request, 'campaigns/assembly_details.html', {
        'assembly': get_object_or_404(Assembly, pk=pk)
    })