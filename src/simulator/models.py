from django.conf import settings
from django.db import models
from zipfile import ZipFile
from pathlib import Path
from django.core.files.base import ContentFile
from django.core.files import File
import shutil
import insillyclo.simulator
import insillyclo.observer
import insillyclo.data_source
import logging
from io import StringIO


# Dynamic function to upload File when creating a job (relative to MEDIA_ROOT)
def job_upload_to(instance, filename):
    return f"simulator/jobs/{instance.job_id}/{filename}"


# Model to store simulation job
class SimulationJob(models.Model):
    job_id = models.CharField(max_length=32, unique=True)
    template = models.FileField(upload_to=job_upload_to)
    preview = models.FileField(upload_to=job_upload_to)
    outputs_zip = models.FileField(upload_to=job_upload_to, blank=True, null=True)
    concentration_file = models.FileField(upload_to=job_upload_to, blank=True, null=True)

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
    def run_simulation(
        self,
        dilution_params=None,
        uploaded_concentration_file=None,
        clear_concentration=False,
        pcr_params=None,
        digestion_params=None,
        uploaded_primers_file=None
    ):
        base = Path(self.template.path).parent
        inputs_dir = base / "inputs"
        output_dir = base / "outputs"
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        inputs_dir.mkdir(parents=True, exist_ok=True)

        # Handle concentration file input
        if clear_concentration:
            if self.concentration_file:
                self.concentration_file.delete(save=False)
            content = ContentFile("pID;Mass Concentration\n")

            self.concentration_file.save("input-plasmid-concentrations.csv", content, save=False)
        elif uploaded_concentration_file:
            if self.concentration_file:
                self.concentration_file.delete(save=False)
            self.concentration_file.save(uploaded_concentration_file.name, uploaded_concentration_file, save=False)
        elif not self.concentration_file:
            content = ContentFile("pID;Mass Concentration\n")
            self.concentration_file.save("input-plasmid-concentrations.csv", content, save=False)
        self.save()

        # Prepare arguments for insillyclo
        kwargs = {
            "observer": insillyclo.observer.InSillyCloCliObserver(debug=True, fail_on_error=True),
            "settings": None,
            "input_template_filled": Path(self.template.path),
            "input_parts_files": [p for p in (inputs_dir / "mapping").rglob("*") if p.is_file()] if (inputs_dir / "mapping").exists() else [],
            "gb_plasmids": [p for p in (inputs_dir / "genbank").rglob("*") if p.is_file()] if (inputs_dir / "genbank").exists() else [],
            "output_dir": output_dir,
            "data_source": insillyclo.data_source.DataSourceHardCodedImplementation(),
            "concentration_file": Path(self.concentration_file.path),
            "sbol_export": False,
        }

        # Dilution parameters
        if dilution_params:
            d = dilution_params
            kwargs.update({
                "default_output_plasmid_volume": float(d.get('final_volume') or 10.0),
                "enzyme_and_buffer_volume": float(d.get('enzyme_buffer_volume') or 2.0),
                "minimal_puncture_volume": float(d.get('minimal_tip_volume') or 0.0),
                "puncture_volume_10x": float(d.get('tip_volume_from_intermediate') or 1.0),
                "minimal_remaining_well_volume": float(d.get('min_remaining_volume_intermediate') or 2.0),
                "expected_concentration_in_output": float(d.get('input_plasmid_concentration_final') or 2.0),
                "default_mass_concentration": float(d.get('default_mass_concentration')) if d.get('default_mass_concentration') else None
            })
            if clear_concentration:
                kwargs["default_mass_concentration"] = None
        
        # PCR parameters
        if pcr_params:
            primers_path = None
            # Handle uploaded primers file
            if uploaded_primers_file:
                target_path = base / uploaded_primers_file.name
                with open(target_path, 'wb+') as f:
                    for chunk in uploaded_primers_file.chunks():
                        f.write(chunk)
                primers_path = target_path

            # Parse primer pairs from text input
            pairs_text = pcr_params.get('pcr_pairs', '')
            primer_id_pairs = []
            for line in pairs_text.strip().split('\n'):
                line = line.replace('\r', '').strip()
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        primer_id_pairs.append((parts[0], parts[1]))
            
            kwargs.update({
                "primers_file": primers_path,
                "primer_id_pairs": primer_id_pairs
            })

        # Digestion parameters
        if digestion_params:
            # Parse enzyme names from text input
            enz_text = digestion_params.get('enzymes', '')
            enzymes = [e.strip() for e in enz_text.replace('\r', '').split('\n') if e.strip()]
            kwargs.update({"enzyme_names": enzymes})

        # Setup logging to capture insillyclo output messages
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger()
        logger.addHandler(handler)

        try:
            # Run the simulator
            insillyclo.simulator.compute_all(**kwargs)

            # Create ZIP of outputs
            zip_path = base / "temp_outputs.zip"
            with ZipFile(zip_path, "w") as z:
                for p in output_dir.rglob("*"):
                    if p.is_file(): z.write(p, p.relative_to(output_dir))

            if self.outputs_zip:
                self.outputs_zip.delete(save=False)
            with zip_path.open("rb") as fh:
                self.outputs_zip.save("outputs.zip", File(fh), save=False)

            zip_path.unlink()

            self.status = "SUCCESS"
            self.error_message = ""
            self.save(update_fields=["outputs_zip", "status", "error_message", "updated_at", "concentration_file"])

        except Exception as e:
            print(f"Error during simulation: {e}")
            handler.flush()
            logs = log_stream.getvalue().strip()
            msg = logs if logs else (str(e) or repr(e))
            # If error comes from uploaded concentration file, display error then reset to default
            if dilution_params:
                self.run_simulation(clear_concentration=True)
            else:
                self.status = "FAIL"
            self.error_message = msg
            self.save(update_fields=["status", "error_message", "updated_at", "concentration_file"])
        finally:
            logger.removeHandler(handler)