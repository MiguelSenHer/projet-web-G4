from django import forms
from django.forms import inlineformset_factory
from .models import Assembly, InputParts

class AssemblyForm(forms.ModelForm):
    class Meta:
        model = Assembly
        fields = [
            "name",
            "comment",
            "separator",
            "restriction_enzyme",
        ]


InputPartsFormSet = inlineformset_factory(
    Assembly,
    InputParts,
    fields=["part_name", "typed", "mandatory", "separator", "allowed_types"],
    extra=1,
    can_delete=True
)
