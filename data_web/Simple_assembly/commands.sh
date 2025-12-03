#!/usr/bin/env bash

insillyclo simulate \
  --input-template-filled Campaign_Venus.xlsx \
  --input-parts-file iP_mapping_Simple.csv \
  --plasmid-repository ../ \
  --recursive-plasmid-repository \
  --default-mass-concentration 200 \
  --plasmid-concentration-file input-plasmid-concentrations_updated.csv \
  --restriction-enzyme-gel BsmBI \
  --primer-pair P29,P30 \
  --primers-file DB_primer.csv \
  --output-dir output_sh/
