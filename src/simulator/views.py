from django.views.generic import FormView
from django.shortcuts import redirect
from django.urls import reverse
import json
from django.http import Http404
from django.core.files.storage import default_storage

from .forms import UploadTemplateForm, UploadInputsForm


class UploadTemplateView(FormView):
    template_name = "simulator/upload_template.html"
    form_class = UploadTemplateForm

    def form_valid(self, form):
        job_id = form.save()
        self.request.session["current_job_id"] = job_id

        return redirect(
            reverse("simulator:preview")
        )


class TemplatePreviewView(FormView):
    template_name = "simulator/preview.html"
    form_class = UploadInputsForm

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("current_job_id"):
            return redirect("simulator:upload_template")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("simulator:preview")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        job_id = self.request.session["current_job_id"]
        json_path = f"simulator/jobs/{job_id}/preview/preview.json"
        if not default_storage.exists(json_path):
            raise Http404("File not found")

        with default_storage.open(json_path, "r") as fp:
            data = json.load(fp)

        context.update({
            "filename": data.get("filename", ""),
            "name": data.get("name", ""),
            "enzyme": data.get("enzyme", ""),
            "separator": data.get("separator", ""),
            "parts": data.get("parts", []),
            "plasmids": data.get("plasmids", []),
        })

        # Open inputs accordion if there are errors
        context["inputs_open"] = bool(context["form"].errors)
        return context

    def form_valid(self, form):
        job_id = self.request.session["current_job_id"]
        form.save(job_id)
        return super().form_valid(form)
