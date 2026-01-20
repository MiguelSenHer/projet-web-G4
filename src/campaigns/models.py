from contextlib import nullcontext
from django.db import models
from django.conf import settings


class SimulationRun(models.Model):
    STATUS_CHOICES = [
        ("RUNNING", "Running"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="simulation_runs",
    )

    run_id = models.CharField(max_length=32, unique=True, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="RUNNING")

    # chemins vers les inputs utilisés pour revenir à la simulation
    template_path = models.CharField(max_length=255)
    genbank_path = models.CharField(max_length=255)
    mapping_path = models.CharField(max_length=255, blank=True)

    # chemin pour le zip output si SUCESS
    output_zip = models.CharField(max_length=255, blank=True)

    # message d'erreur si FAILED
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.run_id} ({self.status})"