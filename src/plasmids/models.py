from django.conf import settings
from django.db import models
from pathlib import Path
from io import StringIO
from django.http import Http404
import shutil
from django.apps import apps

from Bio.SeqFeature import SeqFeature, SimpleLocation
from pycirclize import Circos
from pycirclize.utils import ColorCycler
from pycirclize.parser import Genbank
import matplotlib
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
matplotlib.use("Agg")


class Collection(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    is_public = models.BooleanField(default=False)
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collections",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="uniq_collection_name_per_owner",
            ),
        ]

    def save(self, *args, **kwargs):
        was_public = None
        if self.pk:
            was_public = Collection.objects.get(pk=self.pk).is_public

        super().save(*args, **kwargs)

        if was_public is False and self.is_public is True:
            public_dir = (
                Path(settings.BASE_DIR) / "plasmids" / "public_data" / "collections" / str(self.id)
            )

            public_dir.mkdir(parents=True, exist_ok=True)

            for plasmid in self.plasmids.all():
                src = Path(plasmid.gb_path)
                dst = public_dir / src.name
                shutil.copy2(src, dst)

                plasmid.gb_path = str(dst)
                plasmid.save(update_fields=["gb_path"])
            
            # Copy plasmids
            for plasmid in self.plasmids.all():
                src = Path(plasmid.gb_path)
                dst = public_dir / src.name
                shutil.copy2(src, dst)

                plasmid.gb_path = str(dst)
                plasmid.save(update_fields=["gb_path"])

            # Copy mapping tables
            for mapping in self.mapping_tables.all():
                src = Path(mapping.mapping_path)
                if not src.exists():
                    continue
                dst = public_dir / src.name
                shutil.copy2(src, dst)

                mapping.mapping_path = str(dst)
                mapping.save(update_fields=["mapping_path"])


class MappingTable(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="mapping_tables")
    is_public = models.BooleanField(default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    mapping_path = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Plasmid(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="plasmids")
    name = models.CharField(max_length=200)
    gb_path = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def gb_abspath(self):   
        return Path(apps.get_app_config("plasmids").path) / self.gb_path

    # Visualize plasmid using pycirclize
    def visualize(self, selected_types=None, action=None):
        gb_path = Path(self.gb_path)    
        if not gb_path.exists():
            raise Http404
        
        gbk = Genbank(str(gb_path))

        # Initialize circos instance
        seqid2size = gbk.get_seqid2size()
        space = 0 if len(seqid2size) == 1 else 2
        circos = Circos(sectors=seqid2size, space=space)
        circos.text(f"{self.name}", size=12, r=25)
        seqid2features = gbk.get_seqid2features(feature_type=None)

        # Get feature types present in the genbank file
        all_types = set()
        for features in seqid2features.values():
            for feature in features:
                if feature.type in ("source", "gene"):
                    continue
                all_types.add(feature.type)
        all_types = sorted(all_types)

        # Get selected feature types based on action
        if action == "clear":
            selected_types = []
        elif action == "all":
            selected_types = all_types
        else:
            selected_types = selected_types if selected_types is not None else all_types

        # Assign colors to feature types
        ColorCycler.set_cmap("tab10")
        colors = ColorCycler.get_color_list(len(all_types))
        features_type2color = {t: c for t, c in zip(all_types, colors)}

        # Add features to circos
        for sector in circos.sectors:
            features_track = sector.add_track((90, 100))
            features_track.axis(fc="#EEEEEE", ec="none")

            features = seqid2features.get(sector.name) or []
            features = [f for f in features if f.type in selected_types]
            dupplicates = set()

            for feature in features:
                fc = features_type2color.get(feature.type)

                if feature.location.strand == 1:
                    features_track.genomic_features(feature, plotstyle="arrow", r_lim=(95, 100), fc=fc)
                else:
                    features_track.genomic_features(feature, plotstyle="arrow", r_lim=(90, 95), fc=fc)

                start, end = int(feature.location.start), int(feature.location.end)
                label_pos = (start + end) / 2
                label = feature.qualifiers.get("label", [""])[0]
                if not label:
                    continue

                key = (start, end, label)
                if key in dupplicates:
                    continue
                dupplicates.add(key)
                features_track.annotate(label_pos, label, label_size=10, shorten=None)

            # Add ticks (plasmid length) to sector
            features_track.xticks_by_interval(
                interval=max(1, sector.size // 15),
                outer=False,
                label_formatter=lambda v: f"{v / 1000:.1f} Kb",
                label_orientation="vertical",
                line_kws=dict(ec="grey"),
                show_endlabel=False,
            )

        # Potential restriction sites track 
        enzymes_golden_gate = {
            "BbsI": ("GAAGAC", "GTCTTC"),
            "BsaI": ("GGTCTC", "GAGACC"),
            "Esp3I": ("CGTCTC", "GAGACG"),
            "SapI": ("GCTCTTC", "GAAGAGC"),
            "BtgZI": ("GCGATG", "CATCGC"),
            "PaqCI": ("CACCTGC", "GCAGGTG"),
        }

        # Add track to circos for restriction sites
        seqid2seq = gbk.get_seqid2seq()
        for sector in circos.sectors:
            site_track = sector.add_track((89, 105))
            site_track.axis(fc="none", ec="none")
            seq = str(seqid2seq.get(sector.name, "")).upper()

            for enz_name, (motif_fwd, motif_rev) in enzymes_golden_gate.items():
                for motif in (motif_fwd, motif_rev):
                    motif = motif.upper()
                    i = 0
                    while True:
                        pos = seq.find(motif, i)
                        if pos == -1:
                            break

                        start = pos
                        end = pos + len(motif)
                        mid = (start + end) / 2

                        site_track.genomic_features(
                            SeqFeature(location=SimpleLocation(start, end)),
                            fc="red",
                        )
                        site_track.annotate(
                            mid,
                            enz_name,
                            label_size=12,
                            text_kws=dict(color="red"),
                        )
                        i = pos + 1

        # Generate figure and legend       
        fig = circos.plotfig()
        handles = [Patch(color=features_type2color[t], label=t) for t in selected_types]
        handles.append(Line2D([], [], color="red", label="Potential restriction site", marker="_", ms=6, ls="None"))
        _ = circos.ax.legend(handles=handles, loc="center", bbox_to_anchor=(0.5, 0.475), fontsize=8)

        # Save figure to SVG
        bio = StringIO()
        fig.savefig(bio, format="svg", bbox_inches="tight")

        # Return SVG and feature types info
        return {
            "svg": bio.getvalue(),
            "feature_types": [
                {"type": t, "selected": t in selected_types, "color": features_type2color[t]}
                for t in all_types
            ],
            "restriction_sites_sources": {enz: f"https://www.neb.com/{enz}" for enz in enzymes_golden_gate},
        }
            