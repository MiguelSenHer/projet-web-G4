from contextlib import nullcontext
from django.db import models
from django.conf import settings
from django.core.files.storage import FileSystemStorage


assembly_storage = FileSystemStorage(
    location=str(settings.BASE_DIR / "browse" / "public_data" / "assemblies")
)

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
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assemblies",
    )
    creation_date = models.DateTimeField("Created At")
    separator = models.CharField(max_length=20, choices=SEPARATOR_CHOICES)
    restriction_enzyme = models.CharField(max_length=50, choices=ENZYME_CHOICES)
    file = models.FileField(upload_to="", blank=True, null=True, storage=assembly_storage)
    def __str__(self):
        return self.name
    
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_public = models.BooleanField(default=False)

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
    class Meta:
        ordering = ['type_name'] 
    