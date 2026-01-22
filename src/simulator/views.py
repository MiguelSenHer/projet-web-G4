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

from Bio.SeqFeature import SeqFeature, SimpleLocation
from pycirclize import Circos
from pycirclize.utils import ColorCycler, fetch_genbank_by_accid
from pycirclize.parser import Genbank
from io import StringIO
import matplotlib
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
matplotlib.use("Agg")


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
    

# View to display plasmid diagram
class PlasmidView(TemplateView):
    template_name = "simulator/plasmid_view.html"

    def dispatch(self, request, *args, **kwargs):
        job_id = self.kwargs["job_id"]
        self.job = get_object_or_404(SimulationJob, job_id=job_id)
        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get genbank file
        filename = self.kwargs["filename"]
        base = Path(self.job.template.path).parent
        gb_path = base / "outputs" / f"{filename}.gb"
        gbk = Genbank(str(gb_path))

        # Initialize circos instance
        seqid2size = gbk.get_seqid2size()
        print(seqid2size)
        space = 0 if len(seqid2size) == 1 else 2
        circos = Circos(sectors=seqid2size, space=space)
        circos.text(f"{filename}", size=12, r=25)
        seqid2features = gbk.get_seqid2features(feature_type=None)
        
        # Get feature types present in the genbank file
        all_types = set()
        for features in seqid2features.values():
            for feature in features:
                all_types.add(feature.type)

        # Get selected feature types from the form
        if self.request.method == "POST":
            action = self.request.POST.get("action")
            if action == "clear":
                selected_types = []
            elif action == "all":
                selected_types = sorted(all_types)
            else:
                selected_types = self.request.POST.getlist("feature_types")
        else:
            selected_types = sorted(all_types)
       
        # Assign colors to feature types
        ColorCycler.set_cmap("tab10")
        colors = ColorCycler.get_color_list(len(all_types))
        features_type2color = {type: color for type, color in zip(sorted(all_types), colors)}

        # Add features to circos
        for sector in circos.sectors:
            features_track = sector.add_track((90, 100))
            features_track.axis(fc="#EEEEEE", ec="none")
            features = seqid2features.get(sector.name)
            features = [f for f in features if f.type in selected_types]
            dupplicates = set()

            for feature in features:
                fc = features_type2color.get(feature.type)

                if feature.location.strand == 1:
                    features_track.genomic_features(feature, plotstyle="arrow", r_lim=(95, 100), fc=fc)
                else:
                    features_track.genomic_features(feature, plotstyle="arrow", r_lim=(90, 95), fc=fc)

                start, end = int(feature.location.start), int(feature.location.end)
                label_pos = (start + end) / 2
                label = feature.qualifiers.get("label", [""])[0]
                if label == "":
                    continue
                key = (start, end, label)
                if key in dupplicates:
                    continue
                dupplicates.add(key)
                features_track.annotate(label_pos, label, label_size=10, shorten=None,)
            
            # Add ticks to sector
            features_track.xticks_by_interval(
                interval=sector.size // 15,
                outer=False,
                label_formatter=lambda v: f"{v / 1000:.1f} Kb",
                label_orientation="vertical",
                line_kws=dict(ec="grey"),
                show_endlabel=False,
            )

        # Potential restriction sites track
        enzymes_golden_gate = {
            "BsaI":  "GGTCTC",
            "Esp3I": "CGTCTC",
            "BsmBI-v2": "CGTCTC",
            "BbsI":  "GAAGAC",
            "BtgZI": "GCGATG",
            "AarI":  "CACCTGC",
            "SapI":  "GCTCTTC",
            "BspQI": "GCTCTTC",
            "BfuAI": "ACCTGC",
        }

        # Add track to circos
        seqid2seq = gbk.get_seqid2seq()
        site_track = sector.add_track((89, 105))
        site_track.axis(fc="none", ec="none")
        seq = str(seqid2seq.get(sector.name, ""))

        # Add restriction sites locations
        for enz_name, motif in enzymes_golden_gate.items():
            i = 0
            while True:
                pos = seq.find(motif, i)
                if pos == -1:
                    break

                start = pos
                end = pos + len(motif)
                mid = (start + end) / 2
                site_track.genomic_features(SeqFeature(location=SimpleLocation(start, end)), fc="red")
                site_track.annotate(mid, enz_name, label_size=12, text_kws=dict(color="red"))
                i = pos + 1

        fig = circos.plotfig()

        # Add legend
        handles = [Patch(color=features_type2color[t], label=t) for t in selected_types]
        handles.append(Line2D([], [], color="red", label="Potential restriction site", marker = "_", ms=6, ls="None"))
        _ = circos.ax.legend(handles=handles, loc="center", bbox_to_anchor=(0.5, 0.475), fontsize=8)

        # Save figure to SVG
        bio = StringIO()
        fig.savefig(bio, format="svg", bbox_inches="tight")

        # Return context
        context["svg"] = bio.getvalue()
        context["job_id"] = self.job.job_id
        context["feature_types"] = [
            {
                "type": t,
                "selected": t in selected_types,
                "color": features_type2color[t],
            }
            for t in sorted(all_types)
        ]

        context["restriction_sites_sources"] = {
            "BsaI":  "https://enzymefinder.neb.com/#!/name/BsaI",
            "Esp3I": "https://enzymefinder.neb.com/#!/name/Esp3I",
            "BbsI":  "https://enzymefinder.neb.com/#!/name/BbsI",
            "BtgZI": "https://enzymefinder.neb.com/#!/name/BtgZI",
            "SapI":  "https://enzymefinder.neb.com/#!/name/SapI",
            "AarI":  "https://enzymefinder.neb.com/#!/name/AarI",
            "BfuAI": "https://enzymefinder.neb.com/#!/name/BfuAI",
            "BspQI": "https://enzymefinder.neb.com/#!/name/BspQI",
            "BsmBI-v2": "https://enzymefinder.neb.com/#!/name/BsmBI-v2",
        }

        return context
