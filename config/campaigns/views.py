from django.shortcuts import render
from django.conf import settings
from pathlib import Path
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from .models import Assembly, InputParts, Type

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
<<<<<<< HEAD

            uploaded_name = f.name

    return render(request, "campaigns/load.html", {"uploaded_name": uploaded_name, "error": error})
=======
            request.session["uploaded_template_path"] = str(dest)
            request.session["uploaded_template_name"] = f.name

            return redirect("/campaigns/simulator/upload/")

    return render(request, "campaigns/upload.html", {"error": error})


def upload_template_next(request):
    path_str = request.session.get("uploaded_template_path")
    filename = request.session.get("uploaded_template_name")

    if not path_str:
        return redirect("/campaigns/simulator/upload/")

    try:
        wb = openpyxl.load_workbook(path_str, data_only=True)
        ws = wb.active

        enzyme = _find_value_right(ws, "Restriction enzyme")
        name = _find_value_right(ws, "Name")
        sep = _find_value_right(ws, "Output separator")
        parts = _find_part_names(ws)

        
        assembly = {
            "name": (str(name).strip() if name is not None else (filename or "Unnamed")),
            "separator": (str(sep).strip() if sep is not None else ""),
            "restriction_enzyme": (str(enzyme).strip() if enzyme is not None else ""),
            "input_parts": parts,
        }

        # Verification
        missing = []
        if not assembly["restriction_enzyme"]:
            missing.append("Restriction enzyme")
        if not assembly["name"]:
            missing.append("Name")
        if not assembly["separator"]:
            missing.append("Output separator")
        if not assembly["input_parts"]:
            missing.append("Part name -> row")

        error = None
        if missing:
            error = "Template incomplete: missing " + ", ".join(missing)
        
        is_valid = (len(missing) == 0)
        request.session["template_is_valid"] = is_valid
        request.session["assembly_preview"] = assembly

        return render(request, "campaigns/upload_preview.html", {"assembly": assembly, "error": error})

    except Exception as e:
        return render(request, "campaigns/upload_preview.html", {"assembly": None, "error": str(e)})


def simulator_inputs(request):
    # template validé
    if not request.session.get("template_is_valid", False):
        return redirect("/campaigns/simulator/load/next/")

    assembly = request.session.get("assembly_preview")

    error = None
    ok_genbank = request.session.get("ok_genbank")
    ok_mapping = request.session.get("ok_mapping")


    if request.method == "POST":
        out_dir = Path(settings.MEDIA_ROOT) / "simulator" / "inputs"
        out_dir.mkdir(parents=True, exist_ok=True)

        # --- Upload GenBank ZIP ---
        if request.FILES.get("genbank_zip"):
            f = request.FILES["genbank_zip"]
            if not f.name.lower().endswith(".zip"):
                error = "GenBank input must be a .zip archive."
            else:
                dest = out_dir / f.name
                with open(dest, "wb") as w:
                    for chunk in f.chunks():
                        w.write(chunk)
                request.session["ok_genbank"] = f"GenBank archive uploaded: {f.name}"
                ok_genbank = request.session["ok_genbank"]


        # --- Upload Mapping (csv/tsv/txt OR zip) ---
        if request.FILES.get("mapping_file"):
            f = request.FILES["mapping_file"]
            allowed = (".csv", ".tsv", ".txt", ".zip")
            if not f.name.lower().endswith(allowed):
                error = "Mapping file must be .csv, .tsv, .txt, or .zip."
            else:
                dest = out_dir / f.name
                with open(dest, "wb") as w:
                    for chunk in f.chunks():
                        w.write(chunk)
                request.session["ok_mapping"] = f"Mapping uploaded: {f.name}"
                ok_mapping = request.session["ok_mapping"]

    return render(
        request,
        "campaigns/inputs.html",
        {
            "assembly": assembly,
            "error": error,
            "ok_genbank": ok_genbank,
            "ok_mapping": ok_mapping,
        },
    )
>>>>>>> 56972fd2 (updated upload)


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
    assembly = get_object_or_404(Assembly, id=pk)
    input_parts = assembly.inputparts_set.prefetch_related("allowed_types")
    context = {
        "assembly": assembly,
        "input_parts": input_parts,
    }
    return render(request, "campaigns/assembly_details.html", context)


