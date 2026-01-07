from contextlib import nullcontext
from django.db import models


class Assembly(models.Model):
    name = models.CharField(max_length=200)
    comment = models.TextField()
    creation_date = models.DateTimeField("Created At")
    separator = models.CharField(max_length=20)
    restriction_enzyme = models.CharField(max_length=50)
    file = models.FileField(
        upload_to="assemblies/",
        blank=True,
        null=True
    )


class InputParts(models.Model):
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)
    part_name = models.CharField(max_length=200)
    allowed_types = models.ManyToManyField('Type', related_name='input_parts')
    optional = models.BooleanField(default=False)
    mandatory = models.BooleanField(default=True)
    separator = models.CharField(max_length=20)

class Type(models.Model):
    part = models.ForeignKey(InputParts, on_delete=models.CASCADE)
    type_name = models.CharField(max_length=50)
    