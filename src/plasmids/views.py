from pathlib import Path
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from simulator.models import SimulationJob
from plasmids.models import Collection, Plasmid
from django.contrib import messages
from django.views.generic import ListView, TemplateView
from django.db.models import Q


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
        base = Path(self.job.template.path).parent

        if self.mode == "inputs":
            gb_dir = base / "inputs" / "genbank"
            collection_name = f"Input_plasmids_{self.job.job_id}"
            already_msg = "Input plasmids are already saved in Browse plasmid collections."
            success_msg = "Input plasmids saved to your collection."
        else:
            gb_dir = base / "outputs"
            collection_name = f"Output_plasmids_{self.job.job_id}"
            already_msg = "Output plasmids are already saved in Browse plasmid collections."
            success_msg = "Output plasmids saved to your collection."

        gb_paths = [p for p in gb_dir.rglob("*.gb") if p.is_file()]

        collection, created = Collection.objects.get_or_create(
            owner=request.user,
            name=collection_name,
            defaults={"is_public": False},
        )

        if not created:
            messages.info(request, already_msg)
            return redirect("simulator:simulations_list")

        for p in gb_paths:
            Plasmid.objects.create(
                collection=collection,
                name=p.stem,
                gb_path=str(p),
            )

        messages.success(request, success_msg)
        return redirect("simulator:simulations_list")


# View to browse plasmid collections
class BrowseCollectionsView(ListView):
    model = Collection
    template_name = "plasmids/collections_list.html"
    context_object_name = "collections"

    def get_queryset(self):
        view_filter = self.request.GET.get("view", "all")

        qs = (
            Collection.objects
            .select_related("owner")
            .prefetch_related("plasmids")
            .order_by("-created_at")
        )

        # Not logged in -> only public
        if not self.request.user.is_authenticated:
            return qs.filter(is_public=True)

        # Logged in -> public + mine
        qs = qs.filter(Q(is_public=True) | Q(owner=self.request.user))

        if view_filter == "public":
            qs = qs.filter(is_public=True)
        elif view_filter == "private":
            qs = qs.filter(is_public=False, owner=self.request.user)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "plasmids"
        context["current_filter"] = self.request.GET.get("view", "all")
        return context


# View to display plasmid diagram using job_id + filename (private) or plasmid_id (public)
class PlasmidView(TemplateView):
    template_name = "plasmids/plasmid_view.html"

    def dispatch(self, request, *args, **kwargs):
        # Private mode (job_id + filename)
        if "job_id" in self.kwargs and "filename" in self.kwargs:
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

        # Public mode (plasmid_id)
        if "plasmid_id" in self.kwargs:
            plasmid_id = self.kwargs["plasmid_id"]

            plasmid = get_object_or_404(Plasmid, id=plasmid_id)

            if not plasmid.collection.is_public:
                if (not request.user.is_authenticated) or (plasmid.collection.owner_id != request.user.id):
                    raise Http404
            if not plasmid.gb_abspath().exists():
                raise Http404

            plasmid.gb_path = str(plasmid.gb_abspath())
            self.plasmid = plasmid

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