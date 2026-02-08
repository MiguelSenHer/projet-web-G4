from django.views.generic import FormView, TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from plasmids.models import Collection, MappingCollection
import json
from pathlib import Path
from django.http import Http404, FileResponse
from .forms import UploadTemplateForm, UploadInputsForm
from .models import SimulationJob
import shutil
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from plasmids.models import Plasmid
import pandas as pd


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
        action = request.POST.get("action")
        base_path = Path(settings.MEDIA_ROOT) / "simulator" / "jobs" / self.job.job_id / "inputs"

        # Clear all inputs
        if action == "clear_inputs":
            shutil.rmtree(base_path / "genbank", ignore_errors=True)
            shutil.rmtree(base_path / "mapping", ignore_errors=True)
            messages.success(request, "All inputs were cleared successfully.")
            return redirect("simulator:preview")

        # Add from collections
        elif action == "add_from_collections":
            col_ids = request.POST.getlist("collection_ids")
            col_type = request.POST.get("type")
            results = {"added": [], "skipped": []}
            
            if col_type == "plasmids":
                target_dir = base_path / "genbank"
                target_dir.mkdir(parents=True, exist_ok=True)
                
                collections = Collection.objects.filter(id__in=col_ids)
                for col in collections:
                    # Ensure user has access to the collection (mine or public)
                    if col.owner != request.user and not col.is_public:
                        continue

                    for plasmid in col.plasmids.all():
                        src = plasmid.gb_abspath()
                        print(src)
                        dst = target_dir / src.name
                        if not dst.exists():
                            shutil.copy2(src, dst)
                            results["added"].append(src.name)
                        else:
                            results["skipped"].append(src.name)
                            
            elif col_type == "mappings":
                target_dir = base_path / "mapping"
                target_dir.mkdir(parents=True, exist_ok=True)
                
                collections = MappingCollection.objects.filter(id__in=col_ids)
                for col in collections:
                    # Ensure user has access to the collection (mine or public)
                    if col.owner != request.user and not col.is_public:
                        continue
                    
                    for table in col.tables.all():
                        src = table.mapping_abspath()
                        dst = target_dir / src.name
                        if not dst.exists():
                            shutil.copy2(src, dst)
                            results["added"].append(src.name)
                        else:
                            results["skipped"].append(src.name)

            if results["added"] or results["skipped"]:
                messages.success(
                    request,
                    f"Collection(s) imported succesfully ({len(results['added'])} added, {len(results['skipped'])} skipped)."
                )
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
        context["separator"] = data.get("separator", "")
        context["enzyme"] = data.get("enzyme", "")
        context["parts"] = data.get("parts", [])
        context["plasmids"] = data.get("plasmids", [])

        base = Path(settings.MEDIA_ROOT) / "simulator" / "jobs" / self.job.job_id
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

        # Fetch user's accessible plasmid collections and mapping collections (private and owned or public) 
        if self.request.user.is_authenticated:
            accessible = Q(is_public=True) | Q(owner=self.request.user)
            context["available_collections"] = Collection.objects.filter(accessible)\
                .select_related("owner")\
                .prefetch_related("plasmids")\
                .distinct().order_by('-created_at')
                
            context["available_mappings"] = MappingCollection.objects.filter(accessible)\
                .select_related("owner")\
                .prefetch_related("tables")\
                .distinct().order_by('-created_at')
            
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
            raise Http404
        
        if request.method == "GET":
            self.job.refresh_from_db(fields=["status"])
            if self.job.status == "FAIL":
                return redirect("simulator:preview")
        
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        if action == "run_simulation":
            self.job.run_simulation()

            if self.job.status == "FAIL":
                messages.error(request, self.job.error_message)
                return redirect("simulator:preview")

            return redirect("simulator:run")

        if action == "compute_dilution":
            clear_requested = "clear_file" in request.POST
            self.job.run_simulation(
                dilution_params=request.POST,
                uploaded_concentration_file=request.FILES.get("concentration_file"),
                clear_concentration=clear_requested,
            )
            if clear_requested or request.POST.get("default_mass_concentration", "").strip() == "":
                self.job.has_dilution_results = False
            else:
                self.job.has_dilution_results = not bool(self.job.error_message)
            self.job.save(update_fields=['has_dilution_results'])
            return self.get(request, *args, **kwargs)

        if action == "run_pcr":
            clear_requested = "clear_primers" in request.POST
            self.job.run_simulation(
                pcr_params=request.POST,
                uploaded_primers_file=request.FILES.get("primers_file"),
                clear_primers=clear_requested,
            )
            pcr_pairs = request.POST.get("pcr_pairs", "").strip()
            if clear_requested or pcr_pairs == "" or not self.job.primers_file:
                self.job.has_pcr_results = False
            else:
                self.job.has_pcr_results = not bool(self.job.error_message)

            self.job.save(update_fields=['has_pcr_results'])
            return self.get(request, *args, **kwargs)
        
        if action == "run_digestion":
            self.job.run_simulation(
                digestion_params=request.POST
            )
            enzymes = request.POST.get("enzymes", "").strip()
            if enzymes == "":
                self.job.has_digestion_results = False
            else:
                self.job.has_digestion_results = not bool(self.job.error_message)

            self.job.save(update_fields=["has_digestion_results"])

            return self.get(request, *args, **kwargs)

        return self.get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.job
        storage = job.template.storage
        job_folder = Path(job.template.name).parent
        outputs_dir = job_folder / "outputs"

        # Retrieve previous POST data for dilution parameters
        post_data = self.request.POST
        context["params"] = post_data
        
        # Retrieve dilution CSV files, append URLs and tables
        filenames = [
            ("Direct", "dilution-direct.csv"),
            ("Direct Mastermix", "dilution-direct_mastermix.csv"),
            ("10x", "dilution-10x.csv"),
            ("10x Mastermix", "dilution-10x_mastermix.csv")
        ]

        dilution_tabs = []
        csv_files = []

        if job.has_dilution_results:
            for label, name in filenames:
                file_path = str(outputs_dir / name)
                if not storage.exists(file_path):
                    continue
                csv_files.append({"label": label, "url": storage.url(file_path)})

                try:
                    with storage.open(file_path, "r") as f:
                        df = pd.read_csv(f, sep=",", dtype=str).fillna("")
                        html_table = df.to_html(classes="table table-striped-columns table-bordered table-sm", index=False) 
                except Exception:
                    html_table = "<p class='text-danger'>Could not load table.</p>"
                
                dilution_tabs.append({
                    "name": name,
                    "label": label,
                    "html": html_table
                })

        context["csv_files"] = csv_files
        context["dilution_tabs"] = dilution_tabs

        if job.has_pcr_results:
            pcr_svg_path = outputs_dir / "pcr.svg"
            if storage.exists(str(pcr_svg_path)):
                context["pcr_svg_url"] = storage.url(str(pcr_svg_path))

        if job.has_digestion_results:
            digestion_svg_path = outputs_dir / "digestion.svg"
            if storage.exists(str(digestion_svg_path)):
                context["digestion_svg_url"] = storage.url(str(digestion_svg_path))

        context["job_id"] = job.job_id
        context["status"] = job.status
        context["error"] = job.error_message
        context["concentration_file_name"] = job.concentration_file.name.split("/")[-1] if job.concentration_file else None
        context["concentration_file_url"] = job.concentration_file.url if job.concentration_file else None
        context["primers_file_name"] = job.primers_file.name.split("/")[-1] if job.primers_file else None
        context["primers_file_url"] = job.primers_file.url if job.primers_file else None
        context["outputs_zip_url"] = job.outputs_zip.url if job.outputs_zip else None

        return context


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

            # OUTPUT plasmids
            output_gb_files = []
            outputs_dir = base / "outputs"
            if outputs_dir.exists():
                output_gb_files = [
                    p.name.split(".gb")[0] for p in outputs_dir.rglob("*.gb")
                    if p.is_file()
                ]

            # MAPPING tables
            mapping_files = []
            mapping_dir = base / "inputs" / "mapping"

            if mapping_dir.exists():
                for p in mapping_dir.rglob("*"):
                    if not p.is_file():
                        continue

                    mapping_files.append(
                        (
                            p.name,
                            reverse(
                                "simulator:download_mapping_by_job",
                                args=[job.job_id, p.name],
                            ),
                        )
                    )

            jobs_with_io.append((job, input_gb_files, output_gb_files, mapping_files))

        context["jobs_with_io"] = jobs_with_io
        context["active_page"] = "simulations"
        
        return context


# View to download outputs of a specific job
class DownloadOutputsByJobView(LoginRequiredMixin, View):
    def get(self, request, job_id, *args, **kwargs):
        job = get_object_or_404(SimulationJob, job_id=job_id, user=request.user)

        if not job.outputs_zip:
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

        
# View to display plasmid from a simulation job
class PlasmidView(TemplateView):
    template_name = "plasmids/plasmid_view.html"
    
    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(SimulationJob, job_id=self.kwargs["job_id"])
        
        base = Path(self.job.template.path).parent
        if self.kwargs["mode"] == "outputs":
            full_path = base / "outputs" / f"{self.kwargs['filename']}.gb"
        else:
            full_path = base / "inputs" / "genbank" / f"{self.kwargs['filename']}.gb"

        self.plasmid = Plasmid(name=self.kwargs["filename"], gb_path=str(full_path))
        
        if not Path(self.plasmid.gb_path).exists():
            raise Http404
            
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


# View to visualize mapping table by job_id + filename
class DownloadMappingByJobView(LoginRequiredMixin, View):
    def get(self, request, job_id, filename, *args, **kwargs):
        job = get_object_or_404(SimulationJob, job_id=job_id, user=request.user)

        base = Path(job.template.path).parent
        file_path = base / "inputs" / "mapping" / filename
        if not file_path.exists() or not file_path.is_file():
            raise Http404

        return FileResponse(file_path.open("rb"), as_attachment=False, filename=filename)