from django.shortcuts import render
from django.conf import settings
from pathlib import Path
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
