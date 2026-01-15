import pandas as pd
from django import forms
from django.core.exceptions import ValidationError
from .models import TemplateImport, TemplateRow


# Upload and validation form with minimal parsing of assembly and plasmids for template
class UploadTemplateForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        f = self.cleaned_data["file"]

        # Read excel
        try:
            df = pd.read_excel(f, header=None)
        except Exception:
            raise ValidationError(
                "Invalid file. Only .xlsx allowed. Please check your file."
            )

        # Template fields --> first column
        settings = df.index[df[0] == "Assembly settings"].tolist()
        composition = df.index[df[0] == "Assembly composition"].tolist()
        plasmids = df.index[df[0] == "Output plasmid id ↓"].tolist()

        # Handle missing field
        errs = []
        if not settings:
            errs.append("Missing section: 'Assembly settings'")
        if not composition:
            errs.append("Missing section: 'Assembly composition'")
        if not plasmids:
            errs.append("Missing section: 'Output plasmid id ↓'")
        if errs:
            raise ValidationError(errs)

        # First row of each field
        settings_rows = settings[0]
        composition_rows = composition[0]
        plasmids_rows = plasmids[0]

        # Retrieve settings
        name, separator, enzyme = None, None, None
        for i in range(settings_rows + 1, composition_rows):
            key = str(df.iloc[i, 0])
            val = df.iloc[i, 1]
            if key == "Name" and pd.notna(val):
                name = str(val).strip()
            elif key == "Output separator" and pd.notna(val):
                separator = str(val).strip()
            elif key == "Restriction enzyme" and pd.notna(val):
                enzyme = str(val).strip()

        # Handle missing setting
        if not name:
            errs.append("Missing or empty: 'Name'")
        if not separator:
            errs.append("Missing or empty: 'Output separator'")
        if not enzyme:
            errs.append("Missing or empty: 'Restriction enzyme'")
        if errs:
            raise ValidationError(errs)

        # Check Part name on the right of Assembly composition
        part_row = composition[0]
        if df.iloc[part_row, 1] != "Part name ->":
            raise ValidationError(
                "Missing 'Part name ->' on the right of 'Assembly composition'"
                )

        # Retrieve part on the right of Part name
        parts = []
        for j in range(2, df.shape[1]):
            value = df.iloc[part_row, j]
            if pd.isna(value) or str(value).strip() == "":
                break
            parts.append(str(value).strip())
        if not parts:
            errs.append("No parts detected on the right of 'Part name ->'")
        if errs:
            raise ValidationError(errs)

        # Retrieve output plasmids (pID) in first column,
        # optional output type in second column,
        # and cross pID with Part name as part value of plasmid

        plasmids = []
        for i in range(plasmids_rows+1, df.shape[0]):
            pid = df.iloc[i, 0]
            if pd.isna(pid) or str(pid).strip() == "":
                break
            values = []

            ptype = df.iloc[i, 1]
            ptype = str(ptype).strip() if pd.notna(ptype) else ""
            for j in range(2, 2 + len(parts)):
                value = df.iloc[i, j]
                values.append(str(value).strip() if pd.notna(value) else "")

            plasmids.append({
                "pid": str(pid).strip(),
                "ptype": ptype,
                "part_values": values,
            })

        if not plasmids:
            raise ValidationError(
                "No output rows detected under 'Output plasmid id ↓'"
            )
        self.parsed = {
            "name": name,
            "separator": separator,
            "enzyme": enzyme,
            "parts": parts,
            "plasmids": plasmids,
        }

        return f

    def save(self):
        data = self.parsed
        f = self.cleaned_data["file"]

        imp = TemplateImport.objects.create(
            name=data["name"],
            separator=data["separator"],
            restriction_enzyme=data["enzyme"],
            filename=f.name,
        )

        rows = []
        for out_i, plasmid in enumerate(data["plasmids"], start=1):
            for part_i, (part_name, part_value) in enumerate(
                zip(data["parts"], plasmid["part_values"]),
                start=1,
            ):
                rows.append(
                    TemplateRow(
                        imp=imp,
                        pid=plasmid["pid"],
                        ptype=plasmid["ptype"] or None,
                        part_name=part_name,
                        part_value=part_value,
                    )
                )

        TemplateRow.objects.bulk_create(rows)
        return imp