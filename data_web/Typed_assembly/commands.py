#!/usr/bin/env python3
import pathlib

import insillyclo.data_source
import insillyclo.observer
import insillyclo.simulator

work_dir = pathlib.Path(__file__).parent

observer = insillyclo.observer.InSillyCloCliObserver(
    debug=False,
    fail_on_error=True,
)

output_dir = work_dir / 'output_py'
output_dir.mkdir(parents=True, exist_ok=True)

insillyclo.simulator.compute_all(
    observer=observer,
    settings=None,
    input_template_filled=work_dir / 'Campaign_display_L1.xlsx',
    input_parts_files=[
        work_dir / 'iP_mapping_typed.csv',
    ],
    gb_plasmids=work_dir.glob('../p*/*.gb'),
    output_dir=output_dir,
    data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),
    primers_file=work_dir / 'DB_primer.csv',
    primer_id_pairs=[
        ('P29', 'P30'),
    ],
    enzyme_names=[
        'NotI',
    ],
    default_mass_concentration=200,
    # concentration_file=work_dir / 'input-plasmid-concentrations_updated.csv',
    # default_output_plasmid_volume=...
    # enzyme_and_buffer_volume=...
    # minimal_puncture_volume=...
    # puncture_volume_10x=...,
    # minimal_remaining_well_volume=...
    # expected_concentration_in_output=...
    sbol_export=False,
)
