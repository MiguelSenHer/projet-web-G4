from django.views.generic import FormView
from django.views import View
from django.shortcuts import redirect, render
from django.urls import reverse
import json
from pathlib import Path
import shutil
import zipfile
from django.http import Http404, FileResponse
from django.core.files.storage import default_storage
from .forms import UploadTemplateForm, UploadInputsForm

from .models import SimulationRun

import insillyclo.simulator
import insillyclo.observer
import insillyclo.data_source


# View to upload the template
class UploadTemplateView(FormView):
    template_name = "simulator/upload_template.html"
    form_class = UploadTemplateForm

    def get_success_url(self):
        return reverse("simulator:preview")

    def form_valid(self, form):
        job_id = form.save()
        self.request.session["current_job_id"] = job_id
        return redirect(self.get_success_url())


# View to upload inputs and get inputs preview
class TemplatePreviewView(FormView):
    template_name = "simulator/preview.html"
    form_class = UploadInputsForm

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("current_job_id"):
            return redirect("simulator:upload")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("simulator:preview")

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "clear_inputs":
            self.clear_inputs()
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        job_id = self.request.session["current_job_id"]
        form.save(job_id)
        return redirect(self.get_success_url())

    def clear_inputs(self):
        job_id = self.request.session["current_job_id"]
        base = f"simulator/jobs/{job_id}/inputs"

        for sub_dir in ("genbank", "mapping"):
            sub_path = f"{base}/{sub_dir}"
            if default_storage.exists(sub_path):
                sub_fs_path = Path(default_storage.path(sub_path))
                shutil.rmtree(sub_fs_path, ignore_errors=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        job_id = self.request.session["current_job_id"]
        base = f"simulator/jobs/{job_id}/"

        # Read JSON and add template info to context
        json_path = f"{base}/preview/preview.json"
        if not default_storage.exists(json_path):
            raise Http404("File not found")

        with default_storage.open(json_path, "r") as f:
            data = json.load(f)

        context["filename"] = data.get("filename", "")
        context["name"] = data.get("name", "")
        context["enzyme"] = data.get("enzyme", "")
        context["separator"] = data.get("separator", "")
        context["parts"] = data.get("parts", [])
        context["plasmids"] = data.get("plasmids", [])

        # Read inputs and add (list, paths) of files received to context
        def read_inputs(input_dir_path):
            if not default_storage.exists(input_dir_path):
                return [], []

            _, files = default_storage.listdir(input_dir_path)
            if not files:
                return [], []

            received_files = []
            storage_paths = []

            for file_name in files:
                file_path = f"{input_dir_path}{file_name}"

                if file_name.endswith(".zip"):
                    with default_storage.open(file_path, "rb") as f:
                        with zipfile.ZipFile(f) as z:
                            received_files.extend(n for n in z.namelist() if not n.endswith("/"))
                else:
                    received_files.append(file_name)

                storage_paths.append(file_path)

            return received_files, storage_paths

        context["genbank_files"], context["genbank_paths"] = read_inputs(f"{base}/inputs/genbank/")
        context["mapping_files"], context["mapping_paths"] = read_inputs(f"{base}/inputs/mapping/")

        return context


# View to run simulation based on all inputs
class RunSimulationView(View):
    template_name = "simulator/run.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("current_job_id"):
            return redirect("simulator:upload")
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        job_id = request.session["current_job_id"]

        if request.user.is_authenticated:
            run = SimulationRun.objects.filter(job_id=job_id, user=request.user).first()
            status = run.status if run else None
            error = run.error_message if run else None
        else:
            status = request.session.get("run_status")
            error = request.session.get("run_error")

        return render(request, self.template_name, {
            "job_id": job_id,
            "status": status,
            "error": error,
            "outputs_zip_url": (
                reverse("simulator:download_outputs")
                if run and run.status == "SUCCESS"
                else None
            ),
        })

    def post(self, request, *args, **kwargs):
        job_id = request.session["current_job_id"]
        base = f"simulator/jobs/{job_id}"

        # Inputs from post
        filename = request.POST["filename"]
        enzyme = request.POST["enzyme"]
        genbank_paths = request.POST.getlist("genbank_paths") 
        mapping_paths = request.POST.getlist("mapping_paths") 

        template_path = Path(default_storage.path(f"{base}/inputs/{filename}"))

        # Expand uploaded inputs paths (zip extraction, file depending on extensions)
        def expand_inputs_paths(paths, exts):
            res = []
            for p in paths:
                fp = Path(default_storage.path(p))

                if fp.suffix.lower() == ".zip":
                    extract_dir = fp.parent / f"{fp.stem}"
                    extract_dir.mkdir(parents=True, exist_ok=True)

                    with zipfile.ZipFile(fp) as z:
                        z.extractall(extract_dir)

                    for ext in exts:
                        res.extend(extract_dir.rglob(f"*{ext}"))
                else:
                    if fp.suffix.lower() in exts:
                        res.append(fp)
            return res

        # Note: use a tuple for extensions; (".gb") would be a string
        gb_plasmids = expand_inputs_paths(genbank_paths, (".gb",))

        input_parts_files = expand_inputs_paths(mapping_paths, (".csv", ".tsv", ".txt"))

        # Directory to save outputs
        output_dir_path = Path(default_storage.path(f"{base}/output"))
        output_dir_path.mkdir(parents=True, exist_ok=True)

        # Store run in DB if user authentificated, or in session if anonymous
        if request.user.is_authenticated:
            run, _ = SimulationRun.objects.get_or_create(job_id=job_id, user=request.user)
            run.status = "RUNNING"
            run.error_message = ""
            run.save(update_fields=["status", "error_message", "updated_at"])
        else:
            request.session["run_status"] = "RUNNING"
            request.session["run_error"] = ""

        # Call InsillyClo simulator (python)
        try:
            observer = insillyclo.observer.InSillyCloCliObserver(
                debug=True,
                fail_on_error=True,
            )

            insillyclo.simulator.compute_all(
                observer=observer,
                settings=None,
                input_template_filled=template_path,
                input_parts_files=input_parts_files,
                gb_plasmids=gb_plasmids,
                output_dir=output_dir_path,
                data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),
                enzyme_names=[enzyme],
                default_mass_concentration=200,
                sbol_export=False,
            )

            if request.user.is_authenticated:
                run.status = "SUCCESS"
                run.save(update_fields=["status", "updated_at"])
            else:
                request.session["run_status"] = "SUCCESS"

        except Exception as e:
            error_message = str(e) if str(e) else repr(e)
            if request.user.is_authenticated:
                run.status = "FAIL"
                run.error_message = error_message
                run.save(update_fields=["status", "error_message", "updated_at"])
            else:
                request.session["run_status"] = "FAIL"
                request.session["run_error"] = error_message

        return redirect(reverse("simulator:run"))


# View to download outputs
class DownloadOutputsView(View):
    def get(self, request, *args, **kwargs):
        job_id = request.session.get("current_job_id")
        if not job_id:
            return redirect("simulator:upload")

        if request.user.is_authenticated:
            run = SimulationRun.objects.filter(job_id=job_id, user=request.user).first()
            if not run or run.status != "SUCCESS":
                raise Http404("Run not found")
        else:
            if request.session.get("run_status") != "SUCCESS":
                raise Http404("Run not found")
            
        out_dir = Path(default_storage.path(f"simulator/jobs/{job_id}/output"))
        if not out_dir.exists() or not out_dir.is_dir():
            raise Http404("Run not found")

        zip_base = out_dir.parent / f"outputs_{job_id}"
        zip_path = zip_base.with_suffix(".zip")

        if not zip_path.exists():
            shutil.make_archive(str(zip_base), "zip", root_dir=str(out_dir))

        return FileResponse(open(zip_path, "rb"), as_attachment=True, filename=zip_path.name)
