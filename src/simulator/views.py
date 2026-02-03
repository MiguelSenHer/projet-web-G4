from django.views.generic import FormView, TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from plasmids.models import Collection
import json
from pathlib import Path
from django.http import Http404, FileResponse
from .forms import UploadTemplateForm, UploadInputsForm
from .models import SimulationJob
import shutil
from django.conf import settings
from zipfile import ZipFile
from django.contrib import messages

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

            messages.success(request, "All inputs were cleared successfully.")
            return redirect("simulator:preview")

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        result = form.save(self.job)

        uploaded_names = []
        if "genbank" in self.request.FILES:
            uploaded_names.append(self.request.FILES["genbank"].name)
        if "mapping" in self.request.FILES:
            uploaded_names.append(self.request.FILES["mapping"].name)

        for fname in uploaded_names:
            messages.success(
                self.request,
                (
                    f"Uploaded file: {fname} "
                    f"({len(result['added'])} added, {len(result['skipped'])} skipped)"
                )
            )

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
    template_name = "simulator/simulation_details.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = request.session.get("current_job_id")
        if not job_id:
            return redirect("simulator:upload")

        self.job = get_object_or_404(SimulationJob, job_id=job_id)

        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404("Job not found")

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")

        if action == "run_simulation":
            enzyme = request.POST.get("enzyme", "")
            self.job.enzyme_name = enzyme
            self.job.save(update_fields=["enzyme_name"])
            self.job.run_simulation(enzyme_name=enzyme)
            return redirect("simulator:run")

        if action == "compute_dilution":
            enzyme = self.job.enzyme_name

            self.job.compute_dilution(
                enzyme_name=enzyme,
                default_output_plasmid_volume=request.POST.get("final_volume", "10.0"),
                enzyme_and_buffer_volume=request.POST.get("enzyme_buffer_volume", "2.0"),
                minimal_puncture_volume=request.POST.get("minimal_tip_volume", "0.0"),
                puncture_volume_10x=request.POST.get("tip_volume_from_intermediate", "1.0"),
                minimal_remaining_well_volume=request.POST.get("min_remaining_volume_intermediate", "2.0"),
                expected_concentration_in_output=request.POST.get("input_plasmid_concentration_final", "2.0"),
            )
            return redirect("simulator:run")

        return redirect("simulator:run")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = Path(self.job.template.path).parent

        updated = base / "inputs" / "input-plasmid-concentrations_updated.csv"
        starter = base / "inputs" / "input-plasmid-concentrations.csv"

        current = updated if updated.exists() else starter

        context["concentration_file_name"] = current.name
        context["concentration_file_url"] = (
            self.job.template.storage.url(str(current.relative_to(self.job.template.storage.location)))
        )
        job = self.job
        context["job_id"] = job.job_id
        context["enzyme"] = self.request.POST.get("enzyme", "")
        context["status"] = job.status
        context["error"] = job.error_message
        context["outputs_zip_url"] = reverse("simulator:download_results") if job.status == "SUCCESS" else None
        return context  


# View to download first results of a simulation
class DownloadResultsView(View):
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
        if job.status != "SUCCESS":
            raise Http404

        base = Path(job.template.path).parent
        output_dir = base / "outputs"
        if not output_dir.exists():
            raise Http404

        gb_files = [p for p in output_dir.rglob("*.gb") if p.is_file()]

        csv_db = output_dir / "DB_produced_plasmid.csv"
        csv_autogg = output_dir / "auto-gg-combination-to-make.csv"

        zip_path = base / f"{job.job_id}_results.zip"
        if zip_path.exists():
            zip_path.unlink()

        with ZipFile(zip_path, "w") as z:
            for p in gb_files:
                z.write(p, p.relative_to(output_dir))

            z.write(csv_db, "DB_produced_plasmid.csv")
            z.write(csv_autogg, "auto-gg-combination-to-make.csv")

        return FileResponse(zip_path.open("rb"), as_attachment=True, filename=zip_path.name)


# View to list user's simulation jobs and retrieve inputs/outputs
class SimulationsListView(LoginRequiredMixin, ListView):
    model = SimulationJob
    template_name = "simulator/simulations_list.html"
    context_object_name = "jobs"

    def get_queryset(self):
        return SimulationJob.objects.filter(user=self.request.user).order_by("-updated_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        jobs_with_io = []
        for job in context["jobs"]:
            base = Path(job.template.path).parent

            # INPUT plasmids (uploaded)
            input_gb_files = []
            inputs_dir = base / "inputs" / "genbank"
            if inputs_dir.exists():
                input_gb_files = [
                    p.name.split(".gb")[0] for p in inputs_dir.rglob("*.gb")
                    if p.is_file()
                ]

            # OUTPUT plasmids (produced)
            output_gb_files = []
            outputs_dir = base / "outputs"
            if outputs_dir.exists():
                output_gb_files = [
                    p.name.split(".gb")[0] for p in outputs_dir.rglob("*.gb")
                    if p.is_file()
                ]

            jobs_with_io.append((job, input_gb_files, output_gb_files))

        context["jobs_with_io"] = jobs_with_io
        context["active_page"] = "simulations"
        return context


# View to download outputs of a specific job
class DownloadOutputsByJobView(LoginRequiredMixin, View):
    def get(self, request, job_id, *args, **kwargs):
        job = get_object_or_404(SimulationJob, job_id=job_id, user=request.user)

        if job.status != "SUCCESS" or not job.outputs_zip:
            raise Http404

        return FileResponse(job.outputs_zip.open("rb"), as_attachment=True, filename=f"{job.job_id}_results.zip")


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

        Collection.objects.filter(
            owner=request.user,
            name=f"Simulation {job.job_id}",
            is_public=False,
        ).delete()

        job.delete()
        return redirect("simulator:simulations_list")

        
# View to display plasmid diagram with visualize method from Plasmid model
class PlasmidView(TemplateView):
    template_name = "plasmids/plasmid_view.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.kwargs["job_id"]
        filename = self.kwargs["filename"]
        mode = self.kwargs["mode"]  # "inputs" or "outputs"

        self.job = get_object_or_404(SimulationJob, job_id=job_id)
        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404

        base = Path(self.job.template.path).parent

        if mode == "outputs":
            gb_path = base / "outputs" / f"{filename}.gb"
        elif mode == "inputs":
            gb_path = base / "inputs" / "genbank" / f"{filename}.gb"
        else:
            raise Http404

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
        context["mode"] = self.kwargs["mode"]  # optional, if you want to display it
        return context
