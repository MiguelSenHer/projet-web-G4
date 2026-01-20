from django.conf import settings
from django.db import models

# Dynamic function to upload File when creating a job (relative to MEDIA_ROOT/Simulator)
def job_upload_to(instance, filename):
    if isinstance(instance, SimulationJob):
        return f"simulator/jobs/{instance.job_id}/{filename}"

    if isinstance(instance, InputFile):
        return f"simulator/jobs/{instance.job.job_id}/inputs/{filename}"

# Model to store simulation job
class SimulationJob(models.Model):
    job_id = models.CharField(max_length=32, unique=True)
    template = models.FileField(upload_to=job_upload_to, blank=True, null=True)
    preview = models.FileField(upload_to=job_upload_to, blank=True, null=True)
    genbank_zip = models.FileField(upload_to=job_upload_to, blank=True, null=True)
    mapping = models.FileField(upload_to=job_upload_to, blank=True, null=True)
    outputs_zip = models.FileField(upload_to=job_upload_to, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="simulator_jobs",
    )
    status = models.CharField(max_length=10, default="RUNNING")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# Model to handle multiple Input Files uploads (genbank or mapping)
class InputFile(models.Model):
    job = models.ForeignKey(SimulationJob, on_delete=models.CASCADE, related_name="input_files")
    file_kind = models.CharField(max_length=10)
    file = models.FileField(upload_to=job_upload_to)
