from django.conf import settings
from django.db import models


# Dynamic function to upload File when creating a job (relative to MEDIA_ROOT/Simulator)
def job_upload_to(instance, filename):
    return f"simulator/jobs/{instance.job_id}/{filename}"


# Model to store simulation job
class SimulationJob(models.Model):
    job_id = models.CharField(max_length=32, unique=True)

    template = models.FileField(upload_to=job_upload_to)
    preview = models.FileField(upload_to=job_upload_to)
    outputs_zip = models.FileField(upload_to=job_upload_to, blank=True, null=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="simulator_jobs",
    )

    status = models.CharField(max_length=10)
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
