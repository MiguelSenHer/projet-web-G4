from django.db import models


class TemplateImport(models.Model):
    filename = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    separator = models.CharField(max_length=64)
    restriction_enzyme = models.CharField(max_length=128)


class TemplateRow(models.Model):
    imp = models.ForeignKey(
        TemplateImport,
        on_delete=models.CASCADE,
        related_name="rows"
    )

    pid = models.CharField(max_length=128)
    ptype = models.CharField(max_length=128, blank=True, null=True)
    part_name = models.CharField(max_length=255)
    part_value = models.CharField(max_length=255, blank=True, default="")
