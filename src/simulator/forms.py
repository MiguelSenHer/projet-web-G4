import pandas as pd
from django import forms
from django.core.exceptions import ValidationError
import json
import uuid
from django.core.files.base import ContentFile
import zipfile
from pathlib import Path
from django.conf import settings
from .models import SimulationJob


# Upload and validate template with minimal parsing of assembly and plasmids
class UploadTemplateForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        f = self.cleaned_data["file"]

        # Read excel
        try:
            df = pd.read_excel(f, header=None)
        except Exception:
            raise ValidationError("Invalid .xlsx file")

        # Template fields (first column)
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
            raise ValidationError("Missing 'Part name ->' on the right of 'Assembly composition'")

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

        # Retrieve plasmid ID, plasmid type, and plasmid inputs parts 
        plasmids = []
        for i in range(plasmids_rows + 1, df.shape[0]):
            pid = df.iloc[i, 0]
            if pd.isna(pid) or str(pid).strip() == "":
                break
            values = []

            ptype = df.iloc[i, 1]
            ptype = str(ptype).strip() if pd.notna(ptype) else ""
            for j in range(2, 2 + len(parts)):
                value = df.iloc[i, j]
                values.append(str(value).strip() if pd.notna(value) else "")

            plasmids.append({"pid": str(pid).strip(), "ptype": ptype, "part_values": values})

        if not plasmids:
            raise ValidationError("No output rows detected under 'Output plasmid id ↓'")

        self.parsed = {
            "name": name,
            "separator": separator,
            "enzyme": enzyme,
            "parts": parts,
            "plasmids": plasmids,
        }

        return f

    # Save template and JSON preview and associate to job
    def save(self, user=None):
        data = self.parsed
        f = self.cleaned_data["file"]

        # create job id and job row in DB
        job_id = uuid.uuid4().hex[:10]
        job = SimulationJob.objects.create(job_id=job_id, user=user)

        # save .xlsx template relative to job_id
        job.template.save(f.name, f, save=True)

        # Create JSON preview
        preview = {
            "job_id": job_id,
            "filename": f.name,
            "name": data["name"],
            "separator": data["separator"],
            "enzyme": data["enzyme"],
            "parts": data["parts"],
            "plasmids": data["plasmids"],
        }

        # save JASON preview relative to job_id
        json_file = ContentFile(json.dumps(preview, indent=2).encode("utf-8"))
        job.preview.save("preview.json", json_file, save=True)

        return job


# Upload and validate genbank/mapping and save them
class UploadInputsForm(forms.Form):
    genbank = forms.FileField(required=False)
    mapping = forms.FileField(required=False)

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
                raise ValidationError("GenBank zip may only contain .gb files.")

        return f

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
            raise ValidationError("Invalid mapping file. Only .csv, .tsv, .txt or .zip allowed.")

        for name in z.namelist():
            if name.endswith("/"):
                continue
            if Path(name).suffix.lower() not in (".csv", ".tsv", ".txt"):
                raise ValidationError("Mapping zip may only contain .csv, .tsv or .txt files.")
        return f
    
    # Save input files relative to job and extract if zip
    def save(self, job):
        base = Path(settings.MEDIA_ROOT) / "simulator" / "jobs" / job.job_id / "inputs"

        for kind in ("genbank", "mapping"):
            f = self.cleaned_data.get(kind)
            if not f:
                continue

            dest_dir = base / kind
            dest_dir.mkdir(parents=True, exist_ok=True)

            if f.name.lower().endswith(".zip"):
                with zipfile.ZipFile(f) as z:
                    z.extractall(dest_dir)
            else:
                out = dest_dir / f.name
                with out.open("wb") as dst:
                    for chunk in f.chunks():
                        dst.write(chunk)
        return job
