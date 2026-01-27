from contextlib import nullcontext
from django.db import models
from django.conf import settings


class Assembly(models.Model):
    SEPARATOR_CHOICES = [
        (",", "Comma"),
        ("-", "Hyphen"),
        (".", "Dot"),
        ("~", "Tilde"),
        ("_", "Underscore"),
        (":", "Colon"),
        (";", "Semi-colon"),
        ("/", "Slash"),
        ("\\", "Backslash"),
        ("'", "Apostrophe"),
        ("=", "Equal"),
        ("+", "Plus"),
    ]
    ENZYME_CHOICES = [
        ("BsaI", "BsaI"),
        ("BsmBI", "BsmBI"),
        ("BbsI", "BbsI"),
        ("SapI", "SapI"),
    ]
    name = models.CharField(max_length=200)
    comment = models.TextField(blank=True, null=True)
    creation_date = models.DateTimeField("Created At")
    separator = models.CharField(max_length=20, choices=SEPARATOR_CHOICES)
    restriction_enzyme = models.CharField(max_length=50, choices=ENZYME_CHOICES)
    file = models.FileField(upload_to="projet-web-G4/src/browse/public_data/browse", 
                            blank=True, null=True)
    def __str__(self):
        return self.name

class InputParts(models.Model):
    SEPARATOR_CHOICES = [
        (",", "Comma"),
        ("-", "Hyphen"),
        (".", "Dot"),
        ("~", "Tilde"),
        ("_", "Underscore"),
        (":", "Colon"),
        (";", "Semi-colon"),
        ("/", "Slash"),
        ("\\", "Backslash"),
        ("'", "Apostrophe"),
        ("=", "Equal"),
        ("+", "Plus"),
    ]
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE, related_name='inputparts_set')
    part_name = models.CharField(max_length=200)
    typed = models.BooleanField(default=False)
    mandatory = models.BooleanField(default=True)
    separator = models.CharField(max_length=20, blank=True, null=True, choices=SEPARATOR_CHOICES)
    include_in_output_name = models.BooleanField(default=False)
    allowed_types = models.ManyToManyField('Type', blank=True)

class Type(models.Model):
    type_name = models.CharField(max_length=50)
    def __str__(self):
        return self.type_name