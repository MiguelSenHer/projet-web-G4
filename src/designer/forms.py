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
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter assembly name"
            }),
            "comment": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Optional description of the assembly"
            }),
            "separator": forms.Select(attrs={
                "class": "form-select"
            }),
            "restriction_enzyme": forms.Select(attrs={
                "class": "form-select"
            }),
        }

class InputPartsStyledForm(forms.ModelForm):
    class Meta:
        model = InputParts
        fields = [
            "part_name",
            "typed",
            "mandatory",
            "separator",
            "include_in_output_name",
            "allowed_types",
        ]

        widgets = {
            "part_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter part name"
            }),

            "separator": forms.Select(attrs={
                "class": "form-select"
            }),

            "allowed_types": forms.SelectMultiple(attrs={
                "class": "form-select"
            }),

            "typed": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),

            "mandatory": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),

            "include_in_output_name": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }


InputPartsFormSet = inlineformset_factory(
    Assembly,
    InputParts,
    form=InputPartsStyledForm,
    extra=0,
    can_delete=True
)
