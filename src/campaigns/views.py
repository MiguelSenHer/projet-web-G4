from pathlib import Path
import shutil
import uuid
import zipfile

import pandas as pd
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Assembly, SimulationRun
from .forms import AssemblyForm, InputPartsFormSet

import insillyclo.data_source
import insillyclo.observer
import insillyclo.simulator


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


# Helper to save an uploaded file to MEDIA_ROOT and return its path
def save_upload(f, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(f.name).name
    dest = out_dir / safe_name
    with open(dest, "wb") as w:
        for chunk in f.chunks():
            w.write(chunk)
    return dest


# Helper to parse a campaign template
def parse_template(xlsx_path):

    # Open template and catch bad file
    try:
        df = pd.read_excel(xlsx_path, header=None)
    except Exception as e:
        return {
            "status": "error",
            "errors": [str(e)],
        }

    row_count, col_count = df.shape
    errors = []

    # Locate sections
    settings_r = df.index[df[0] == "Assembly settings"].tolist()
    compo_r = df.index[df[0] == "Assembly composition"].tolist()
    output_r = df.index[df[0] == "Output plasmid id ↓"].tolist()

    # Verify sections exist
    if not settings_r:
        errors.append("Missing section: 'Assembly settings'")
    if not compo_r:
        errors.append("Missing section: 'Assembly composition'")
    if not output_r:
        errors.append("Missing section: 'Output plasmid id ↓'")

    if errors:
        return {"errors": errors, "status": "error"}

    # First row of each section
    s_r, c_r, o_r = settings_r[0], compo_r[0], output_r[0]

    # Retrieve right input of section
    name, sep, enzyme = "Unnamed", "", ""
    for i in range(s_r + 1, c_r):
        key = str(df.iloc[i, 0]).strip()
        val = df.iloc[i, 1]
        if key == "Name":
            name = str(val).strip() if pd.notna(val) else name
        elif key == "Output separator":
            sep = str(val).strip() if pd.notna(val) else ""
        elif key == "Restriction enzyme":
            v_str = str(val).lower().strip()
            enzyme = "" if v_str in ("na", "n.a.", "nan") or pd.isna(val) else str(val).strip()
    
    if not enzyme:
        errors.append("Missing or empty: 'Restriction enzyme'")
    if not sep:
        errors.append("Missing or empty: 'Output separator'")
    if not name or name == "Unnamed":
        errors.append("Missing or empty: 'Name'")

    # Find part names
    part_name_row = None
    for i in range(c_r, o_r):
        if str(df.iloc[i, 1]).strip() == "Part name ->":
            part_name_row = i
            break

    # Verify part name exists
    if part_name_row is None:
        errors.append("Missing Part name -> in Assembly composition.")
        return {"errors": errors, "status": "error"}

    # Extract parts
    parts = []
    for j in range(2, col_count):
        v = df.iloc[part_name_row, j]
        if pd.isna(v) or str(v).strip() == "":
            break
        parts.append(str(v).strip())
    if not parts:
        errors.append("No parts detected (row 'Part name ->' empty).")

    # Extract outputs
    outputs = []
    for i in range(o_r + 1, row_count):
        pid = df.iloc[i, 0]
        if pd.isna(pid) or str(pid).strip() == "":
            break
        
        part_vals = []
        for j in range(2, 2 + len(parts)):
            cell_v = df.iloc[i, j] if j < col_count else None
            part_vals.append(str(cell_v).strip() if pd.notna(cell_v) else "")
        
        outputs.append({
            "pid": str(pid).strip(),
            "ptype": str(df.iloc[i, 1]).strip() if pd.notna(df.iloc[i, 1]) else "",
            "part_values": part_vals
        })

    return {
        "name": name,
        "separator": sep,
        "restriction_enzyme": enzyme,
        "input_parts": parts,
        "output_parts": parts,
        "output_rows": outputs,
        "errors": errors,
        "status": "error" if errors else "ok"
    }


# Helper to validate extensions in a zip
def zip_only_contains_extensions(
        zip_path: Path,
        allowed_exts: set[str],
        *,
        allow_empty=False):
    
    allowed_exts = {e.lower() for e in allowed_exts}

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = [n for n in zf.namelist() if n and not n.endswith("/")]
    except zipfile.BadZipFile:
        return False, "Uploaded file is not a valid .zip archive (corrupted)."

    if not names and not allow_empty:
        return False, "The .zip archive is empty."

    for n in names:
        lower = n.lower()
        if not any(lower.endswith(ext) for ext in allowed_exts):
            ext_list = ", ".join(sorted(allowed_exts))
            return (
                False, 
                f"Invalid file in archive: '{n}'. Only {ext_list} allowed."
            )

    return True, None


# View to start a new simulation
def simulator_home(request):
    # Reset session
    for k in SESSION_KEYS:
        request.session.pop(k, None)
    request.session.modified = True

    options = [
        {
            "label": "LOAD YOUR PLASMID ASSEMBLY TEMPLATE",
            "url": "/campaigns/simulator/upload/"
        },
        {
            "label": "BROWSE PLASMID ASSEMBLY TEMPLATE",
            "url": "/campaigns/simulator/browse/"},
    ]
    return render(
        request,
        "campaigns/template.html",
        {"options": options, "active_page": "simulator"}
        )


def upload_template(request):
    error = None
    # Clear uploaded input
    if request.method == "POST" and request.POST.get("clear_template") == "1":
        for k in ["uploaded_template_path",
                  "uploaded_template_name",
                  "template_is_valid",
                  "assembly_preview"]:
            request.session.pop(k, None)
        request.session.modified = True
        return redirect("/campaigns/simulator/upload/")

    # Request .xlsx
    if request.method == "POST" and request.FILES.get("template_file"):
        f = request.FILES["template_file"]
        if not f.name.lower().endswith(".xlsx"):
            error = "Only .xlsx files are allowed."
        else:
            dest = save_upload(f, Path(settings.MEDIA_ROOT) / "simulator" / "templates")
            request.session["uploaded_template_path"] = str(dest)
            request.session["uploaded_template_name"] = Path(f.name).name
            request.session.modified = True
            return redirect("/campaigns/simulator/upload/")

    return render(
        request,
        "campaigns/upload.html", 
        {"error": error}
        )


# View to upload, validate template, and preview assembly
def upload_template_next(request):
    xlsx_path = request.session.get("uploaded_template_path")
    filename = request.session.get("uploaded_template_name")

    # Require an uploaded .xlsx
    if not xlsx_path:
        return redirect("/campaigns/simulator/upload/")

    # Retrieve all data from the template
    data = parse_template(xlsx_path)

    # If parser has errors
    if data["status"] != "ok":
        request.session["template_is_valid"] = False
        request.session["assembly_preview"] = None
        request.session.modified = True

    # Return parser errors
        return render(
            request,
            "campaigns/upload_preview.html",
            {
                "assembly": None,
                "error": "\n".join(data.get("errors", [])),
                "active_page": "simulator",
            },
        )

    # Else Create assembly
    assembly = {
        "name": data["name"] or (filename or "Unnamed"),
        "separator": data["separator"],
        "restriction_enzyme": data["restriction_enzyme"],
        "input_parts": data["input_parts"],
    }

    # Valide assembly (no errors)
    request.session["template_is_valid"] = True
    request.session["assembly_preview"] = assembly
    request.session.modified = True

    return render(
        request,
        "campaigns/upload_preview.html",
        {"assembly": assembly, "error": None, "active_page": "simulator"},
    )


# View to upload inputs
def simulator_inputs(request):
    # Require validated template
    if not request.session.get("template_is_valid", False):
        return redirect("/campaigns/simulator/upload/next/")

    # Get assembly preview
    assembly = request.session.get("assembly_preview")
    error = None

    # Clear genbank
    if request.method == "POST" and request.POST.get("clear_genbank") == "1":
        for k in ["genbank_path", "genbank_name", "ok_genbank"]:
            request.session.pop(k, None)
        request.session.modified = True
        return redirect("/campaigns/simulator/inputs/")
    
    # Clear mapping
    if request.method == "POST" and request.POST.get("clear_mapping") == "1":
        for k in ["mapping_path", "mapping_name", "ok_mapping"]:
            request.session.pop(k, None)
        request.session.modified = True
        return redirect("/campaigns/simulator/inputs/")

    if request.method == "POST":
        out_dir = Path(settings.MEDIA_ROOT) / "simulator" / "inputs"

        # GenBank zip (required)
        if request.FILES.get("genbank_zip"):
            f = request.FILES["genbank_zip"]
            if not f.name.lower().endswith(".zip"):
                error = "GenBank input must be a .zip archive."
            else:
                # Verify extensions in zip
                dest = save_upload(f, out_dir)
                ok, msg = zip_only_contains_extensions(dest, {".gb", ".gbk", ".genbank"})
                if not ok:
                    dest.unlink(missing_ok=True)
                    for k in ["genbank_path", "genbank_name", "ok_genbank"]:
                        request.session.pop(k, None)
                    error = msg
                else:
                    request.session["genbank_path"] = str(dest)
                    request.session["genbank_name"] = Path(f.name).name
                    request.session["ok_genbank"] = True
                    request.session.modified = True

        # Mapping (optional)
        if request.FILES.get("mapping_file"):
            f = request.FILES["mapping_file"]
            name_lower = f.name.lower()

            # Require zip or table
            if not name_lower.endswith((".csv", ".tsv", ".txt", ".zip")):
                error = "Mapping file must be .csv, .tsv, .txt, or .zip."
            else:
                dest = save_upload(f, out_dir)
                # If zip, verify inside file extensions
                if name_lower.endswith(".zip"):
                    ok, msg = zip_only_contains_extensions(dest, {".csv", ".tsv", ".txt"})
                    if not ok:
                        dest.unlink(missing_ok=True)
                        for k in ["mapping_path", "mapping_name", "ok_mapping"]:
                            request.session.pop(k, None)
                        error = msg
                    else:
                        request.session["mapping_path"] = str(dest)
                        request.session["mapping_name"] = Path(f.name).name
                        request.session["ok_mapping"] = True
                        request.session.modified = True
                else:
                    request.session["mapping_path"] = str(dest)
                    request.session["mapping_name"] = Path(f.name).name
                    request.session["ok_mapping"] = True
                    request.session.modified = True

    return render(
        request,
        "campaigns/inputs.html",
        {
            "assembly": assembly,
            "error": error,
            "ok_genbank": request.session.get("ok_genbank"),
            "ok_mapping": request.session.get("ok_mapping"),
            "genbank_name": request.session.get("genbank_name"),
            "mapping_name": request.session.get("mapping_name"),
        },
    )


# View to print simulation preview
def simulation_preview(request):
    # Require valide template
    if not request.session.get("template_is_valid", False):
        return redirect("/campaigns/simulator/upload/next/")
    
    # View for received files
    def list_received_files(path_str: str | None):
        if not path_str:
            return []
        p = Path(path_str)
        if not p.exists():
            return []
        if p.suffix.lower() == ".zip" and zipfile.is_zipfile(p):
            with zipfile.ZipFile(p, "r") as z:
                return sorted([Path(n).name for n in z.namelist() if n and not n.endswith("/") and Path(n).name])
        return [p.name]

    # Get received files
    genbank_files = list_received_files(request.session.get("genbank_path"))
    mapping_files = list_received_files(request.session.get("mapping_path"))

    # Get template
    template_path = request.session.get("uploaded_template_path")

    # Get assembly preview
    assembly = request.session.get("assembly_preview")
    output_parts, output_rows, output_error = [], [], None

    if template_path:
        data = parse_template(template_path)

        if data.get("status") == "ok":
            assembly = {
                "name": data.get("name", ""),
                "separator": data.get("separator", ""),
                "restriction_enzyme": data.get("restriction_enzyme", ""),
                "input_parts": data.get("input_parts", []),
            }
            output_parts = data.get("output_parts", [])
            output_rows = data.get("output_rows", [])
        else:
            output_error = "\n".join(data.get("errors", []))

    return render(
        request,
        "campaigns/simulation_preview.html",
        {
            "assembly": assembly,
            "genbank_files": genbank_files,
            "mapping_files": mapping_files,
            "genbank_count": len(genbank_files),
            "mapping_count": len(mapping_files),
            "output_parts": output_parts,
            "output_rows": output_rows,
            "output_error": output_error,
        },
    )


# View to browse templates
def browse_templates(request):
    assemblies = Assembly.objects.prefetch_related("inputparts_set")
    return render(request, "campaigns/browse.html", {"assemblies": assemblies, "active_page": "browse"})


# View to download the .xlsx associated with a template 
def assembly_download(request, pk):
    assembly = get_object_or_404(Assembly, pk=pk)
    if not assembly.file_name:
        raise Http404("No file associated with this assembly")

    file_path = Path(settings.BASE_DIR) / "assemblies_files" / assembly.file_name
    if not file_path.exists():
        raise Http404("File not found")

    return FileResponse(open(file_path, "rb"), as_attachment=True, filename=assembly.file_name)


# View to check details of an assembly
def assembly_detail(request, pk):
    assembly = get_object_or_404(Assembly, id=pk)
    input_parts = assembly.inputparts_set.prefetch_related("allowed_types")
    return render(
        request,
        "campaigns/assembly_details.html",
        {
            "assembly": assembly,
            "input_parts": input_parts,
            "active_page": "browse"
        }
    )


# View to run a simulation
def simulation_run(request):
    # Require validated template
    if not request.session.get("template_is_valid"):
        return redirect("/campaigns/simulator/upload/next/")

    # Request input paths
    template_path = request.session.get("uploaded_template_path")
    genbank_zip_path = request.session.get("genbank_path")
    mapping_path = request.session.get("mapping_path")  # optional

    if not template_path:
        return redirect("/campaigns/simulator/upload/")
    if not genbank_zip_path:
        return redirect("/campaigns/simulator/inputs/")

    # Request assembly details
    assembly = request.session.get("assembly_preview") or {}
    enzyme = assembly.get("restriction_enzyme") or ""

    # Create a run directory associated with simulation id
    run_id = uuid.uuid4().hex[:10]
    run_dir = Path(settings.MEDIA_ROOT) / "simulator" / "runs" / run_id
    repo_dir = run_dir / "plasmid_repository"
    map_dir = run_dir / "mapping"
    out_dir = run_dir / "output"
    for d in (repo_dir, map_dir, out_dir):
        d.mkdir(parents=True, exist_ok=True)

    run = None

    # Create a run in database if user is connected
    if request.user.is_authenticated:
        run = SimulationRun.objects.create(
            user=request.user,
            run_id=run_id,
            status="RUNNING",
            template_path=template_path,
            genbank_path=genbank_zip_path,
            mapping_path=mapping_path or "",
        )

    try:
        # Extract GenBank zip
        with zipfile.ZipFile(genbank_zip_path, "r") as zf:
            zf.extractall(repo_dir)

        gb_plasmids = list(repo_dir.rglob("*.gb")) + list(repo_dir.rglob("*.gbk"))
        if not gb_plasmids:
            raise ValueError("No GenBank files found in the uploaded archive.")

        # Get mapping files (optional)
        input_parts_files = []
        if mapping_path:
            mp = Path(mapping_path)
            if mp.suffix.lower() == ".zip":
                with zipfile.ZipFile(mp, "r") as zf:
                    zf.extractall(map_dir)
                input_parts_files = list(map_dir.rglob("*.csv")) + list(map_dir.rglob("*.tsv")) + list(map_dir.rglob("*.txt"))
            else:
                input_parts_files = [mp]

        # Run simulation via Python
        # call inspired by commands.py
        observer = insillyclo.observer.InSillyCloCliObserver(
            debug=True,
            fail_on_error=True,
        )

        insillyclo.simulator.compute_all(
            observer=observer,
            settings=None,
            input_template_filled=Path(template_path),
            input_parts_files=input_parts_files,
            gb_plasmids=gb_plasmids,
            output_dir=out_dir,
            data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),
            enzyme_names=[enzyme] if enzyme else [],
            default_mass_concentration=200,
            sbol_export=False,
        )

        # Zip outputs
        zip_path = run_dir / "outputs.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in out_dir.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(out_dir).as_posix())

        if run is not None:
            run.status = "SUCCESS"
            run.output_zip = str(zip_path.relative_to(settings.MEDIA_ROOT))
            run.save(update_fields=["status", "output_zip", "updated_at"])

        request.session["last_run_id"] = run_id
        request.session.modified = True

        return render(
            request,
            "campaigns/simulation_run.html",
            {
                "assembly": request.session.get("assembly_preview"),
                "status": "ok",
                "error": None,
                "run_id": run_id,
                "outputs_zip_url": f"/campaigns/simulator/run/{run_id}/download/",
                "is_authenticated": request.user.is_authenticated,
            },
        )

    except Exception as e:

        # Get error message or error type
        error_raised = str(e) if str(e) else e.__class__.__name__
        if run is not None:
            run.status = "FAILED"
            run.error_message = error_raised
            run.save(update_fields=["status", "error_message", "updated_at"])

        return render(
            request,
            "campaigns/simulation_run.html",
            {
                "assembly": request.session.get("assembly_preview"),
                "status": "error",
                "error": run.error_message,
                "run_id": run_id,
                "outputs_zip_url": None,
                "is_authenticated": request.user.is_authenticated,
            },
        )


def simulation_run_download(request, run_id):
    if request.session.get("last_run_id") != run_id:
        raise Http404("Not allowed.")

    zip_path = Path(settings.MEDIA_ROOT) / "simulator" / "runs" / run_id / "outputs.zip"
    if not zip_path.exists():
        raise Http404("File not found.")

    return FileResponse(open(zip_path, "rb"), as_attachment=True, filename=f"outputs_{run_id}.zip")


@login_required(login_url="/accounts/login/")
def simulations_list(request):
    runs = SimulationRun.objects.filter(user=request.user).order_by("-updated_at")
    items = [
        {
            "run_id": r.run_id,
            "status": r.status,
            "updated_at": r.updated_at,
            "download_url": f"/campaigns/simulator/run/{r.run_id}/download/" if r.status == "SUCCESS" else None,
            "back_url": f"/campaigns/simulator/run/{r.run_id}/resume/",
        }
        for r in runs
    ]
    return render(request, "campaigns/simulations_list.html", {"items": items, "active_page": "simulations"})

# View to go back to a run of a user
@login_required
def resume_run(request, run_id):
    run = get_object_or_404(SimulationRun, run_id=run_id, user=request.user)

    # Clear session
    for k in SESSION_KEYS:
        request.session.pop(k, None)

    request.session["uploaded_template_path"] = run.template_path
    request.session["genbank_path"] = run.genbank_path
    if run.mapping_path:
        request.session["mapping_path"] = run.mapping_path

    data = parse_template(run.template_path)

    if data.get("status") != "ok":
        request.session["template_is_valid"] = False
        request.session["assembly_preview"] = None
        request.session.modified = True
        return redirect("/campaigns/simulator/upload/next/")
    
    assembly = {
        "name": data.get("name", "Unnamed"),
        "separator": data.get("separator", ""),
        "restriction_enzyme": data.get("restriction_enzyme", ""),
        "input_parts": data.get("input_parts", []),
    }
    
    request.session["assembly_preview"] = assembly
    request.session["template_is_valid"] = True
    request.session.modified = True

    return redirect("/campaigns/simulator/preview/")

# View to delete the media associated to a run of a user that are in page Simulations
@login_required
def delete_run(request, run_id):
    if request.method != "POST":
        return redirect("/campaigns/simulator/simulations/")

    run = get_object_or_404(SimulationRun, run_id=run_id, user=request.user)
    run_dir = Path(settings.MEDIA_ROOT) / "simulator" / "runs" / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)

    run.delete()
    return redirect("/campaigns/simulator/simulations/")

# View to start a new simulation
def design_home(request):
    # Reset session
    for k in SESSION_KEYS:
        request.session.pop(k, None)
    request.session.modified = True

    options = [
        {
            "label": "CREATE",
            "url": "/campaigns/designer/properties/"
        },
        {
            "label": "BROWSE EXISTING",
            "url": ""},
    ]
    return render(
        request,
        "campaigns/designer_home.html",
        {"options": options, "active_page": "designer"}
        )


def designer_properties(request):
    assembly = None
    if request.method == "POST":
        form = AssemblyForm(request.POST, instance=assembly)
        if form.is_valid():
            assembly = form.save(commit=False)
            assembly.creation_date = timezone.now()
            assembly.save()
            return redirect("designer_input_parts", pk=assembly.pk)
    else:
        form = AssemblyForm()
    return render(request, "campaigns/designer_properties.html", {"form": form, "assembly":assembly})


def designer_input_parts(request, pk):
    assembly = get_object_or_404(Assembly, pk=pk)
    if request.method == "POST":
        formset = InputPartsFormSet(request.POST, instance=assembly)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for obj in instances:
                obj.assembly = assembly
                obj.save()
            formset.save_m2m()  # ← THIS WAS MISSING
            return redirect("designer_summary", pk=assembly.pk)
    else:
        formset = InputPartsFormSet(instance=assembly)
    return render(
        request,
        "campaigns/designer_input_parts.html",
        {"assembly": assembly, "formset": formset}
    )

    
def designer_summary(request, pk):
    assembly = get_object_or_404(Assembly, pk=pk)
    if request.method == "POST":
        return redirect("assembly_detail", pk=assembly.pk)
    return render(
        request,
        "campaigns/designer_summary.html",
        {"assembly": assembly}
    )




