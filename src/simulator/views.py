from django.views.generic import FormView, DetailView
from django.shortcuts import redirect
from django.urls import reverse

from .forms import UploadTemplateForm
from .models import TemplateImport


class UploadTemplateView(FormView):
    template_name = "simulator/upload_template.html"
    form_class = UploadTemplateForm

    def form_valid(self, form):
        imp = form.save()
        return redirect(
            reverse("simulator:preview", kwargs={"pk": imp.id})
        )


class TemplatePreviewView(DetailView):
    model = TemplateImport
    template_name = "simulator/preview_uploaded_template.html"
    context_object_name = "imp"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        rows = self.object.rows.all()  # TemplateRow
        parts = sorted({r.part_name for r in rows})
        plasmids = sorted({r.pid for r in rows})

        # (pid, part_name) -> (ptype, value)
        cell = {}
        ptype_map = {}
        for r in rows:
            cell[(r.pid, r.part_name)] = r.part_value
            if r.pid not in ptype_map:
                ptype_map[r.pid] = r.ptype or ""

        matrix = []
        for pid in plasmids:
            matrix.append({
                "pid": pid,
                "ptype": ptype_map.get(pid, ""),
                "values": [cell.get((pid, part), "") for part in parts],
            })

        ctx["parts"] = parts
        ctx["matrix"] = matrix
        return ctx
