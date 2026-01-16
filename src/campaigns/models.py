from contextlib import nullcontext
from django.db import models
from django.conf import settings


class Assembly(models.Model):
    name = models.CharField(max_length=200)
    comment = models.TextField()
    creation_date = models.DateTimeField("Created At")
    separator = models.CharField(max_length=20)
    restriction_enzyme = models.CharField(max_length=50)
    file_name = models.CharField(max_length=255, blank=True, null=True)



class InputParts(models.Model):
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE, related_name='inputparts_set')
    part_name = models.CharField(max_length=200)
    typed = models.BooleanField(default=False)
    mandatory = models.BooleanField(default=True)
    separator = models.CharField(max_length=20, blank=True, null=True)
    allowed_types = models.ManyToManyField('Type', blank=True)

class Type(models.Model):
    type_name = models.CharField(max_length=50)

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