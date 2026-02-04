from django.conf import settings
from django.db import models
from zipfile import ZipFile
from pathlib import Path
from django.core.files import File
import shutil
import insillyclo.simulator
import insillyclo.observer
import insillyclo.data_source


# Dynamic function to upload File when creating a job (relative to MEDIA_ROOT/Simulator)
def job_upload_to(instance, filename):
    return f"simulator/jobs/{instance.job_id}/{filename}"


# Model to store simulation job
class SimulationJob(models.Model):
    job_id = models.CharField(max_length=32, unique=True)
    enzyme_name = models.CharField(max_length=50)
    template = models.FileField(upload_to=job_upload_to)
    preview = models.FileField(upload_to=job_upload_to)
    outputs_zip = models.FileField(upload_to=job_upload_to, blank=True, null=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="simulator_jobs",
    )

    status = models.CharField(max_length=10, default="PENDING")
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Run simulation using insillyclo 
    def run_simulation(self, *, enzyme_name=None, dilution_params=None, uploaded_concentration_file=None):
        base = Path(self.template.path).parent
        inputs_dir = base / "inputs"
        output_dir = base / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Concentration file path
        concentration_file = inputs_dir / "input-plasmid-concentrations.csv"

        # Handle concentration file input
        if uploaded_concentration_file:
            # If the user uploads their filled file, we save it
            inputs_dir.mkdir(parents=True, exist_ok=True)
            with open(concentration_file, 'wb+') as destination:
                for chunk in uploaded_concentration_file.chunks():
                    destination.write(chunk)
        # If no file is provided, create an empty one with header 
        elif not concentration_file.exists():
            inputs_dir.mkdir(parents=True, exist_ok=True)
            with open(concentration_file, 'w', encoding='utf-8') as f:
                f.write("pID;Mass Concentration\n")

        # Prepare arguments for insillyclo
        kwargs = {
            "observer": insillyclo.observer.InSillyCloCliObserver(debug=True, fail_on_error=True),
            "settings": None,
            "input_template_filled": Path(self.template.path),
            "input_parts_files": [p for p in (inputs_dir / "mapping").rglob("*") if p.is_file()] if (inputs_dir / "mapping").exists() else [],
            "gb_plasmids": [p for p in (inputs_dir / "genbank").rglob("*") if p.is_file()] if (inputs_dir / "genbank").exists() else [],
            "output_dir": output_dir,
            "data_source": insillyclo.data_source.DataSourceHardCodedImplementation(),
            "enzyme_names": [enzyme_name or self.enzyme_name],
            "concentration_file": concentration_file,
            "sbol_export": False,
        }

        # Dilution parameters
        if dilution_params:
            kwargs.update({
                "default_output_plasmid_volume": float(dilution_params.get('final_volume', 10.0)),
                "enzyme_and_buffer_volume": float(dilution_params.get('enzyme_buffer_volume', 2.0)),
                "minimal_puncture_volume": float(dilution_params.get('minimal_tip_volume', 0.0)),
                "puncture_volume_10x": float(dilution_params.get('tip_volume_from_intermediate', 1.0)),
                "minimal_remaining_well_volume": float(dilution_params.get('min_remaining_volume_intermediate', 2.0)),
                "expected_concentration_in_output": float(dilution_params.get('input_plasmid_concentration_final', 2.0)),
            })

        try:
            # Run the simulator
            insillyclo.simulator.compute_all(**kwargs)

            # Overwrite concentration file if it was auto-generated
            generated_csv = output_dir / "input-plasmid-concentrations.csv"
            if generated_csv.exists() and not uploaded_concentration_file:
                shutil.copy2(generated_csv, concentration_file)

            # Save outputs as zip file
            zip_path = base / "outputs.zip"
            if zip_path.exists():
                zip_path.unlink()

            with ZipFile(zip_path, "w") as z:
                for p in output_dir.rglob("*"):
                    if p.is_file():
                        z.write(p, p.relative_to(output_dir))

            with zip_path.open("rb") as fh:
                if self.outputs_zip:
                    self.outputs_zip.delete(save=False)
                self.outputs_zip.save("outputs.zip", File(fh), save=False)

            zip_path.unlink()   

            self.status = "SUCCESS"
            self.error_message = ""
            self.save(update_fields=["outputs_zip", "status", "error_message", "updated_at"])

        except Exception as e:
            self.status = "FAIL"
            self.error_message = str(e) or repr(e)
            self.save(update_fields=["status", "error_message", "updated_at"])