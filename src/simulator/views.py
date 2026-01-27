from django.views.generic import FormView, TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
import json
from pathlib import Path
from zipfile import ZipFile
from django.http import Http404, FileResponse
from .forms import UploadTemplateForm, UploadInputsForm
from .models import SimulationJob
import shutil
from django.conf import settings

import insillyclo.simulator
import insillyclo.observer
import insillyclo.data_source

from plasmids.models import Plasmid


# View to start a new simulation
class SimulatorHomeView(TemplateView):
    template_name = "simulator/home.html"

    def dispatch(self, request, *args, **kwargs):
        request.session.pop("current_job_id", None)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "simulator"
        return context


# View to upload the template
class UploadTemplateView(FormView):
    template_name = "simulator/upload_template.html"
    form_class = UploadTemplateForm

    def form_valid(self, form):
        user = self.request.user if self.request.user.is_authenticated else None
        job = form.save(user=user)
        self.request.session["current_job_id"] = job.job_id
        return redirect("simulator:preview")


# View to upload inputs and get inputs preview
class TemplatePreviewView(FormView):
    template_name = "simulator/preview.html"
    form_class = UploadInputsForm

    def dispatch(self, request, *args, **kwargs):
        job_id = request.session.get("current_job_id")
        if not job_id:
            return redirect("simulator:upload")

        self.job = get_object_or_404(SimulationJob, job_id=job_id)

        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "clear_inputs":
            base = Path(self.job.template.path).parent

            shutil.rmtree(base / "inputs" / "genbank", ignore_errors=True)
            shutil.rmtree(base / "inputs" / "mapping", ignore_errors=True)
            return redirect("simulator:preview")

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save(self.job)
        return redirect("simulator:preview")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        with self.job.preview.open("rb") as f:
            data = json.load(f)

        context["filename"] = data.get("filename", "")
        context["name"] = data.get("name", "")
        context["enzyme"] = data.get("enzyme", "")
        context["separator"] = data.get("separator", "")
        context["parts"] = data.get("parts", [])
        context["plasmids"] = data.get("plasmids", [])

        base = Path(self.job.template.path).parent
        genbank_dir = base / "inputs" / "genbank"
        mapping_dir = base / "inputs" / "mapping"

        context["genbank_files"] = (
            [p.name for p in genbank_dir.rglob("*") if p.is_file()] 
            if genbank_dir.exists() else []
        )
        context["mapping_files"] = (
            [p.name for p in mapping_dir.rglob("*") if p.is_file()]
            if mapping_dir.exists() else []
        )

        return context


# View to run the simulation
class RunSimulationView(TemplateView):
    template_name = "simulator/run.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = request.session.get("current_job_id")
        if not job_id:
            return redirect("simulator:upload")

        self.job = get_object_or_404(SimulationJob, job_id=job_id)

        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404("Job not found")

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        base = Path(self.job.template.path).parent
        genbank_dir = base / "inputs" / "genbank"
        mapping_dir = base / "inputs" / "mapping"

        gb_files = (
            [p for p in genbank_dir.rglob("*") if p.is_file()]
            if genbank_dir.exists() else []
        )

        mapping_files = (
            [p for p in mapping_dir.rglob("*") if p.is_file()]
            if mapping_dir.exists() else []
        )

        output_dir = base / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            insillyclo.simulator.compute_all(
                observer=insillyclo.observer.InSillyCloCliObserver(
                    debug=True, fail_on_error=True
                ),
                settings=None,
                input_template_filled=Path(self.job.template.path),
                input_parts_files=mapping_files,
                gb_plasmids=gb_files,
                output_dir=output_dir,
                data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),
                enzyme_names=[request.POST.get("enzyme", "")],
                default_mass_concentration=200,
                sbol_export=False,
            )

            zip_path = base / "outputs.zip"
            if zip_path.exists():
                zip_path.unlink()

            with ZipFile(zip_path, "w") as z:
                for p in output_dir.rglob("*"):
                    if p.is_file():
                        z.write(p, p.relative_to(output_dir))

            self.job.outputs_zip.name = f"simulator/jobs/{self.job.job_id}/outputs.zip"
            self.job.status = "SUCCESS"
            self.job.error_message = ""
            self.job.save(update_fields=["outputs_zip", "status", "error_message", "updated_at"])

        except Exception as e:
            self.job.status = "FAIL"
            self.job.error_message = str(e) or repr(e)
            self.job.save(update_fields=["status", "error_message", "updated_at"])

        return redirect("simulator:run")
   
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        job = get_object_or_404(SimulationJob, job_id=self.request.session["current_job_id"])

        context["job_id"] = job.job_id
        context["status"] = job.status
        context["error"] = job.error_message
        context["outputs_zip_url"] = reverse("simulator:download_outputs") if job.status == "SUCCESS" else None

        return context


# View to download outputs of a simulation
class DownloadOutputsView(View):
    def dispatch(self, request, *args, **kwargs):
        job_id = request.session.get("current_job_id")

        if not job_id:
            return redirect("simulator:upload") 
        self.job = get_object_or_404(SimulationJob, job_id=job_id)

        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        job = self.job

        if job.status != "SUCCESS" or not job.outputs_zip:
            raise Http404

        return FileResponse(job.outputs_zip.open("rb"), as_attachment=True, filename="outputs.zip")


# View to list user's simulation jobs
class SimulationsListView(LoginRequiredMixin, ListView):
    model = SimulationJob
    template_name = "simulator/simulations_list.html"
    context_object_name = "jobs"

    def get_queryset(self):
        return (SimulationJob.objects.filter(user=self.request.user).order_by("-updated_at"))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        jobs_with_outputs = []
        for job in context["jobs"]:
            gb_files = []
            outputs_dir = Path(job.template.path).parent / "outputs"
            if outputs_dir.exists():
                gb_files = [
                    p.name.split(".gb")[0] for p in outputs_dir.rglob("*.gb")
                    if p.is_file()
                ]
            jobs_with_outputs.append((job, gb_files))

        context["jobs_with_outputs"] = jobs_with_outputs
        context["active_page"] = "simulations"

        return context


# View to download outputs of a specific job
class DownloadOutputsByJobView(LoginRequiredMixin, View):
    def get(self, request, job_id, *args, **kwargs):
        job = get_object_or_404(SimulationJob, job_id=job_id, user=request.user)

        if job.status != "SUCCESS" or not job.outputs_zip:
            raise Http404

        return FileResponse(job.outputs_zip.open("rb"), as_attachment=True, filename="outputs.zip")


# View to resume a simulation from the simulations list
class ResumeSimulationView(LoginRequiredMixin, View):
    def post(self, request, job_id, *args, **kwargs):
        job = get_object_or_404(SimulationJob, job_id=job_id)

        if job.user_id != request.user.id:
            raise Http404("Job not found")

        request.session["current_job_id"] = job.job_id
        return redirect("simulator:preview")
    

# View to delete a simulation job from the simulations list
class DeleteSimulationView(LoginRequiredMixin, View):
    def post(self, request, job_id, *args, **kwargs):
        job = get_object_or_404(SimulationJob, job_id=job_id, user=request.user)

        job_dir = Path(settings.MEDIA_ROOT) / "simulator" / "jobs" / job.job_id
        shutil.rmtree(job_dir, ignore_errors=True)

        job.delete()
        return redirect("simulator:simulations_list")
    

# View to display plasmid diagram with visualize method from Plasmid model
class PlasmidView(TemplateView):
    template_name = "plasmids/plasmid_view.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.kwargs["job_id"]
        filename = self.kwargs["filename"]

        self.job = get_object_or_404(SimulationJob, job_id=job_id)
        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404
      
        base = Path(self.job.template.path).parent
        gb_path = base / "outputs" / f"{filename}.gb"
        if not gb_path.exists():
            raise Http404
      
        self.plasmid = Plasmid(name=filename, gb_path=str(gb_path))

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.method == "POST":
            action = self.request.POST.get("action")
            selected_types = self.request.POST.getlist("feature_types")
        else:
            action = None
            selected_types = None
        
        context.update(self.plasmid.visualize(selected_types=selected_types, action=action))

        context["job_id"] = self.job.job_id
        context["plasmid_name"] = self.plasmid.name
        return context
