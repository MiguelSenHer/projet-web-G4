from django import forms
from django.forms import inlineformset_factory
from browse.models import Assembly, InputParts

class AssemblyForm(forms.ModelForm):
    class Meta:
        model = Assembly
        fields = [
            "name",
            "comment",
            "separator",
            "restriction_enzyme",
            "is_public",
        ]


InputPartsFormSet = inlineformset_factory(
    Assembly,
    InputParts,
    fields=["part_name", "typed", "mandatory", "separator", "include_in_output_name", "allowed_types"],
    extra=0,
    can_delete=True
)
