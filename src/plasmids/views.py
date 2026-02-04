from pathlib import Path
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from simulator.models import SimulationJob
from plasmids.models import Collection, Plasmid, MappingTable, MappingCollection
from django.contrib import messages
from django.views.generic import ListView, TemplateView
from django.db.models import Q
from django.http import FileResponse
from django.conf import settings
from django.core.exceptions import PermissionDenied
import io
import zipfile


# View to save input/output plasmids from a simulation job to a user's collection
class SaveCollectionView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.mode = self.kwargs["mode"]  # "inputs" or "outputs"
        job_id = self.kwargs["job_id"]

        if self.mode not in ("inputs", "outputs"):
            raise Http404

        self.job = get_object_or_404(SimulationJob, job_id=job_id)
        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        job_id = self.job.job_id
        base = Path(settings.MEDIA_ROOT) / "simulator" / "jobs" / job_id

        if self.mode == "inputs":
            gb_dir = base / "inputs" / "genbank"
            collection_name = f"Input_plasmids_{job_id}"
        else:
            gb_dir = base / "outputs"
            collection_name = f"Output_plasmids_{job_id}"

        gb_files = [p for p in gb_dir.glob("*.gb") if p.is_file()]

        collection, _ = Collection.objects.get_or_create(
            owner=request.user,
            name=collection_name,
            simulation_job=self.job,
            defaults={"is_public": False},
        )

        existing_paths = set(collection.plasmids.values_list("gb_path", flat=True))
        
        created_count = 0
        skipped_count = 0

        for p in gb_files:
            if self.mode == "inputs":
                gb_path = f"simulator/jobs/{job_id}/inputs/genbank/{p.name}"
            else:
                gb_path = f"simulator/jobs/{job_id}/outputs/{p.name}"

            if gb_path not in existing_paths:
                Plasmid.objects.create(
                    collection=collection,
                    name=p.stem,
                    gb_path=gb_path,
                )
                created_count += 1
            else:
                skipped_count += 1

        if created_count > 0:
            messages.success(request, f"Plasmids saved: {created_count} added, {skipped_count} already present.")
        else:
            messages.info(request, "All plasmids from this job were already in your collection.")

        return redirect("simulator:simulations_list")


# View to save mapping tables from a simulation job 
class SaveMappingView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        job_id = self.kwargs["job_id"]
        self.job = get_object_or_404(SimulationJob, job_id=job_id)
        if self.job.user_id is not None and self.job.user_id != request.user.id:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        job_id = self.job.job_id
        job_dir = Path(settings.MEDIA_ROOT) / "simulator" / "jobs" / job_id
        mapping_dir = job_dir / "inputs" / "mapping"

        if not mapping_dir.exists():
            messages.info(request, "No mapping tables found.")
            return redirect("simulator:simulations_list")

        files = [
            p for p in mapping_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in (".csv", ".tsv", ".txt")
        ]

        if not files:
            messages.info(request, "No mapping tables found.")
            return redirect("simulator:simulations_list")

        collection_name = f"Mapping_tables_{job_id}"
        collection, _ = MappingCollection.objects.get_or_create(
            owner=request.user,
            name=collection_name,
            simulation_job=self.job,
            defaults={"is_public": False}
        )

        existing_paths = set(collection.tables.values_list("mapping_path", flat=True))

        created = 0
        skipped = 0

        for p in files:
            mapping_path = f"simulator/jobs/{job_id}/inputs/mapping/{p.name}"

            if mapping_path not in existing_paths:
                MappingTable.objects.create(
                    collection=collection,
                    owner=request.user,
                    mapping_path=mapping_path,
                    name=p.name,
                    is_public=False,
                )
                created += 1
            else:
                skipped += 1

        if created:
            messages.success(request, f"Saved to {collection_name}: {created} added, {skipped} skipped.")
        else:
            messages.info(request, "All files were already in this collection.")

        return redirect("simulator:simulations_list")


# View to browse plasmid and mapping collections
class BrowseCollectionsView(ListView):
    model = Collection
    template_name = "plasmids/collection_list.html"
    context_object_name = "collections"

    def get_queryset(self):
        view_filter = self.request.GET.get("view", "all")
        qs = Collection.objects.select_related("owner").prefetch_related("plasmids").order_by("-created_at")

        if not self.request.user.is_authenticated:
            qs = qs.filter(is_public=True)
        else:
            qs = qs.filter(Q(is_public=True) | Q(owner=self.request.user))

        if view_filter == "public":
            qs = qs.filter(is_public=True)
        elif view_filter == "private" and self.request.user.is_authenticated:
            qs = qs.filter(is_public=False, owner=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        view_filter = self.request.GET.get("view", "all")
        context["active_page"] = "plasmids"
        context["current_filter"] = view_filter

        mqs = MappingCollection.objects.select_related("owner").prefetch_related("tables").order_by("-created_at")

        if not self.request.user.is_authenticated:
            mqs = mqs.filter(is_public=True)
        else:
            mqs = mqs.filter(Q(is_public=True) | Q(owner=self.request.user))

        if view_filter == "public":
            mqs = mqs.filter(is_public=True)
        elif view_filter == "private" and self.request.user.is_authenticated:
            mqs = mqs.filter(is_public=False, owner=self.request.user)

        context["mapping_collections"] = mqs
        return context


# View to display plasmid diagram using job_id + filename (private) or plasmid_id (public)
class PlasmidView(TemplateView):
    template_name = "plasmids/plasmid_view.html"

    def dispatch(self, request, *args, **kwargs):
        if "plasmid_id" in self.kwargs:
            self.plasmid = get_object_or_404(Plasmid, id=self.kwargs["plasmid_id"])
            
            if not self.plasmid.collection.is_public:
                if self.plasmid.collection.owner != request.user:
                    raise Http404

            if not self.plasmid.gb_abspath().exists():
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

        if "job_id" in self.kwargs:
            context["job_id"] = self.kwargs["job_id"]

        context["plasmid_name"] = self.plasmid.name

        return context


# View to visualize a mapping table file
class MappingView(View):
    def get(self, request, mapping_id, *args, **kwargs):
        mapping = get_object_or_404(MappingTable, id=mapping_id)
        if not mapping.collection.is_public:
            if not request.user.is_authenticated or mapping.collection.owner_id != request.user.id:
                raise Http404

        file_path = mapping.mapping_abspath()
        
        if not file_path.exists():
            raise Http404

        return FileResponse(open(file_path, "rb"), content_type="text/csv")
    
# View to download a plasmid collection as a ZIP file
def DownloadCollectionView(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    
    if not collection.is_public:
        if not request.user.is_authenticated or collection.owner != request.user:
            raise PermissionDenied

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        for plasmid in collection.plasmids.all():
            file_path = plasmid.gb_abspath()
            if file_path.exists():
                zf.write(file_path, arcname=f"{plasmid.name}.gb")
    buffer.seek(0)

    return FileResponse(buffer, as_attachment=True, filename=f"{collection.name}.zip")


# View to download a mapping collection as a ZIP file
def DownloadMappingCollectionView(request, collection_id):
    collection = get_object_or_404(MappingCollection, id=collection_id)
    
    if not collection.is_public:
        if not request.user.is_authenticated or collection.owner != request.user:
            raise PermissionDenied

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        for table in collection.tables.all():
            path = table.mapping_abspath()
            if path.exists():
                zf.write(path, arcname=table.name)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"{collection.name}.zip")