from django.views.generic import FormView, TemplateView
from django.views import View
from django.shortcuts import redirect, render
from django.urls import reverse
import json
from pathlib import Path
import shutil
from django.http import Http404, FileResponse
from django.core.files.storage import default_storage
from .forms import UploadTemplateForm, UploadInputsForm
from .models import SimulationJob
import insillyclo.simulator
import insillyclo.observer
import insillyclo.data_source
from glob import glob


# View to start a new simulation
class SimulatorHomeView(TemplateView):
    template_name = "simulator/home.html"

    def dispatch(self, request, *args, **kwargs):
        # Reset session
        request.session.pop("current_job_id", None)
        request.session.modified = True
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        options = [
            {
                "label": "LOAD YOUR PLASMID ASSEMBLY TEMPLATE",
                "url": reverse("simulator:upload"),
            },
            {
                "label": "BROWSE PLASMID ASSEMBLY TEMPLATE",
                "url": reverse("browse:browse_templates"),
            },
        ]

        context["options"] = options
        context["active_page"] = "simulator"
        return context


# View to upload the template
class UploadTemplateView(FormView):
    template_name = "simulator/upload_template.html"
    form_class = UploadTemplateForm

    def get_success_url(self):
        return reverse("simulator:preview")

    def form_valid(self, form):
        user = self.request.user if self.request.user.is_authenticated else None
        job = form.save(user=user)
        self.request.session["current_job_id"] = job.job_id
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

    def get_job(self):
        job_id = self.request.session["current_job_id"]
        job = SimulationJob.objects.filter(job_id=job_id).first()
        if not job:
            raise Http404("Job not found")
        return job

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "clear_inputs":
            job = self.get_job()
            job.input_files.all().delete()
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        job = self.get_job()
        form.save(job)
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        job = self.get_job()
        if not job.preview:
            raise Http404("File not found")

        with job.preview.open("r") as f:
            data = json.load(f)

        context["filename"] = data.get("filename", "")
        context["name"] = data.get("name", "")
        context["enzyme"] = data.get("enzyme", "")
        context["separator"] = data.get("separator", "")
        context["parts"] = data.get("parts", [])
        context["plasmids"] = data.get("plasmids", [])

        genbank_qs = job.input_files.filter(file_kind="genbank").order_by("id")
        mapping_qs = job.input_files.filter(file_kind="mapping").order_by("id")

        context["genbank_files"] = [x.file.name.split("/")[-1] for x in genbank_qs]
        context["mapping_files"] = [x.file.name.split("/")[-1] for x in mapping_qs]
        context["genbank_paths"] = [x.file.name for x in genbank_qs]
        context["mapping_paths"] = [x.file.name for x in mapping_qs]

        return context


# View to run the simulation
class RunSimulationView(TemplateView):
    template_name = "simulator/run.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("current_job_id"):
            return redirect("simulator:upload")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        job_id = self.request.session["current_job_id"]
        job = SimulationJob.objects.filter(job_id=job_id).first()
    
        enzyme = request.POST.get("enzyme", "")

        base = Path(job.template.path).parent

        gb_files = [Path(p) for p in glob(f"{base}/inputs/genbank/*")]
        mapping_files = [Path(p) for p in glob(f"{base}/inputs/mapping/*")]

        output_dir = base / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        job.status = "RUNNING"
        job.error_message = ""
        job.save(update_fields=["status", "error_message", "updated_at"])

        try:
            observer = insillyclo.observer.InSillyCloCliObserver(
                debug=True,
                fail_on_error=True
            )

            insillyclo.simulator.compute_all(
                observer=observer,
                settings=None,
                input_template_filled=Path(job.template.path),
                input_parts_files=mapping_files,
                gb_plasmids=gb_files,
                output_dir=output_dir,
                data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),
                enzyme_names=[enzyme],
                default_mass_concentration=200,
                sbol_export=False,
            )

            zip_base = output_dir.parent / "outputs"
            zip_path = zip_base.with_suffix(".zip")
            if zip_path.exists():
                zip_path.unlink()
            shutil.make_archive(str(zip_base), "zip", root_dir=str(output_dir))

            if job.outputs_zip:
                job.outputs_zip.delete(save=False)
            with open(zip_path, "rb") as f:
                job.outputs_zip.save(zip_path.name, f, save=True)

            job.status = "SUCCESS"
            job.save(update_fields=["status", "updated_at"])

        except Exception as e:
            job.status = "FAIL"
            error =  str(e) if str(e) else repr(e)
            job.error_message = error
            print(f"Simulation failed: {error}")
            job.save(update_fields=["status", "error_message", "updated_at"])

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
