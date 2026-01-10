from contextlib import nullcontext
from django.db import models


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
    