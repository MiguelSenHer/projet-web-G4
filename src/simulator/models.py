from django.db import models
from django.conf import settings


class SimulationRun(models.Model):
    job_id = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="runs"
    )
    status = models.CharField(max_length=10, default="RUNNING")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
