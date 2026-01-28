from django.conf import settings
from django.db import models
from zipfile import ZipFile
from pathlib import Path
from django.core.files import File
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

    # Run simulation using insillyclo (first results)
    def run_simulation(self, *, enzyme_name=None):
        base = Path(self.template.path).parent

        genbank_dir = base / "inputs" / "genbank"
        mapping_dir = base / "inputs" / "mapping"

        gb_files = [p for p in genbank_dir.rglob("*") if p.is_file()] if genbank_dir.exists() else []
        mapping_files = [p for p in mapping_dir.rglob("*") if p.is_file()] if mapping_dir.exists() else []

        output_dir = base / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            insillyclo.simulator.compute_all(
                observer=insillyclo.observer.InSillyCloCliObserver(
                    debug=True,
                    fail_on_error=True
                ),
                settings=None,
                input_template_filled=Path(self.template.path),
                input_parts_files=mapping_files,
                gb_plasmids=gb_files,
                output_dir=output_dir,
                data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),
                enzyme_names=[enzyme_name or ""],
                sbol_export=False,
            )

            # Create starter input concentrations file (shortened to output plasmids)
            concentration_starter = base / "inputs" / "input-plasmid-concentrations.csv"
            if not concentration_starter.exists():
                output_gb = [p for p in output_dir.glob("*.gb") if p.is_file()]

                with concentration_starter.open("w", encoding="utf-8") as f:
                    f.write("pID;Mass Concentration\n")
                    for p in output_gb:
                        f.write(f"{p.stem};\n")

            # Zip outputs
            zip_path = base / "outputs.zip"
            if zip_path.exists():
                zip_path.unlink()

            with ZipFile(zip_path, "w") as z:
                for p in output_dir.rglob("*"):
                    if p.is_file():
                        z.write(p, p.relative_to(output_dir))

            # Save to file field in model (upload_to)
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
    
    # Compute dilution
    def compute_dilution(
        self,
        *,
        enzyme_name=None,
        default_output_plasmid_volume=10.0,
        enzyme_and_buffer_volume=2.0,
        minimal_puncture_volume=0.0,
        puncture_volume_10x=1.0,
        minimal_remaining_well_volume=2.0,
        expected_concentration_in_output=2.0,
    ):
        base = Path(self.template.path).parent

        genbank_dir = base / "inputs" / "genbank"
        mapping_dir = base / "inputs" / "mapping" 
        output_dir = base / "outputs"

        gb_files = [p for p in genbank_dir.rglob("*") if p.is_file()] if genbank_dir.exists() else []
        mapping_files = [p for p in mapping_dir.rglob("*") if p.is_file()] if mapping_dir.exists() else []

        concentration_file = base / "inputs" / "input-plasmid-concentrations_updated.csv"
        if not concentration_file.exists():
            concentration_file = base / "inputs" / "input-plasmid-concentrations.csv"

        try:
            insillyclo.simulator.compute_all(
                observer=insillyclo.observer.InSillyCloCliObserver(debug=True, fail_on_error=True),
                settings=None,
                input_template_filled=Path(self.template.path),
                input_parts_files=mapping_files,
                gb_plasmids=gb_files,
                output_dir=output_dir,
                data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),
                enzyme_names=[enzyme_name or ""],
                concentration_file=concentration_file,
                default_output_plasmid_volume=float(default_output_plasmid_volume),
                enzyme_and_buffer_volume=float(enzyme_and_buffer_volume),
                minimal_puncture_volume=float(minimal_puncture_volume),
                puncture_volume_10x=float(puncture_volume_10x),
                minimal_remaining_well_volume=float(minimal_remaining_well_volume),
                expected_concentration_in_output=float(expected_concentration_in_output),
                sbol_export=False,
            )

            # Zip outputs
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
