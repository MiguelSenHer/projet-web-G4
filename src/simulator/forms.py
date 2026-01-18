import pandas as pd
from django import forms
from django.core.exceptions import ValidationError
import json
import uuid
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import zipfile
from pathlib import Path


# Upload and validate template with minimal parsing of assembly and plasmids
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

    # Save templated and JSON preview and associate to job id
    def save(self):
        data = self.parsed
        f = self.cleaned_data["file"]

        # create job id
        job_id = uuid.uuid4().hex[:10]

        # save .xlsx in MEDIA_ROOT relative to job_id
        default_storage.save(f"simulator/jobs/{job_id}/inputs/{f.name}", f)

        # JSON preview
        preview = {
            "job_id": job_id,
            "filename": f.name,
            "name": data['name'],
            "separator": data["separator"],
            "enzyme": data["enzyme"],
            "parts": data["parts"],
            "plasmids": data["plasmids"]
        }

        # save .json in MEDIA_ROOT relative to job_id
        default_storage.save(
            f"simulator/jobs/{job_id}/preview/preview.json",
            ContentFile(json.dumps(preview, indent=2)),
        )

        return job_id


# View to upload genbank and mapping and save them
class UploadInputsForm(forms.Form):
    genbank = forms.FileField(required=False)
    mapping = forms.FileField(required=False)

    # For genbank only a zip containaing .gb files allowed
    def clean_genbank(self):
        f = self.cleaned_data.get("genbank")
        if not f:
            return None

        try:
            z = zipfile.ZipFile(f)
        except Exception:
            raise ValidationError("Invalid GenBank zip. Only .zip allowed.")

        for name in z.namelist():
            if name.endswith("/"):
                continue
            if Path(name).suffix.lower() != ".gb":
                raise ValidationError(
                    "GenBank zip may only contain .gb files."
                )

        return f
    
    # For mapping only csv txt tsv or zip containing them allowed
    def clean_mapping(self):
        f = self.cleaned_data.get("mapping")
        if not f:
            return None

        ext = Path(f.name).suffix.lower()

        if ext in (".csv", ".tsv", ".txt"):
            return f

        try:
            z = zipfile.ZipFile(f)
        except Exception:
            raise ValidationError(
                "Invalid mapping zip. Only .csv, .tsv, .txt or a zip allowed."
            )

        for name in z.namelist():
            if name.endswith("/"):
                continue
            if Path(name).suffix.lower() not in (".csv", ".tsv", ".txt"):
                raise ValidationError(
                    "Mapping zip may only contain .csv, .tsv or .txt files."
                )

        return f

    # Save genbank and mapping in MEDIA_ROOT relative to job_id with extraction and list
    def save(self, job_id):

        # GenBank ZIP
        genbank = self.cleaned_data.get("genbank")
        if genbank:
            path = f"simulator/jobs/{job_id}/inputs/genbank/{genbank.name}"
            if default_storage.exists(path):
                default_storage.delete(path)
            default_storage.save(path, genbank)

        mapping = self.cleaned_data.get("mapping")
        if mapping:
            path = f"simulator/jobs/{job_id}/inputs/mapping/{mapping.name}"
            if default_storage.exists(path):
                default_storage.delete(path)
            default_storage.save(path, mapping)
