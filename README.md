# Measurement-defined blood pressure elevation and clinically recognized hypertension as prediction targets

## Overview
Code accompanying a manuscript prepared for submission to BMC Public Health. The study compares two observable hypertension targets while holding baseline participants, information and prediction procedures constant. Neither target is treated as ground truth. The manuscript is not described as published and no DOI is assigned.

## Study design
- CHARLS: development and longitudinal discovery, 2013–2015.
- ELSA: external longitudinal evaluation, waves 4–6.
- HRS: external longitudinal evaluation, 2014–2018.
- NHANES: cross-sectional benchmark, 2015–2016.

## Definitions
M is measurement-defined current BP elevation: mean SBP >=140 mmHg or DBP >=90 mmHg under source-specific measurement rules. R is source-native reported physician/health-professional recognition. T is reported BP-lowering treatment, used as contextual/sensitivity information and not primary eligibility. Unknown and routed responses are not recoded as negative. See [variable definitions](documentation/VARIABLE_DEFINITIONS.md).

## Repository scope
This repository contains code, authored method documentation and source-interface configuration. It contains no source participant data, participant predictions, fitted model files or aggregate numerical source datasets. Acquire data independently and process them in a separate, access-controlled local workspace. No original private Git history is imported.

## Data access
Obtain CHARLS through [authorized CHARLS access](https://charls.pku.edu.cn); ELSA through [ELSA/UK Data Service](https://www.elsa-project.ac.uk/data-and-documentation); HRS through [authorized HRS access](https://hrsdata.isr.umich.edu); and NHANES through [CDC/NCHS](https://www.cdc.gov/nchs/nhanes). Follow the applicable source terms, citations and redistribution restrictions. See [DATA_ACCESS.md](DATA_ACCESS.md) for required local interfaces and HRS precautions.

## Analysis workflow
The exact execution order and original-to-public filename mapping are in [ANALYSIS_WORKFLOW.md](documentation/ANALYSIS_WORKFLOW.md). Paths are configured with `DATA_ROOT`, `PROJECT_ROOT` and `SOURCE_CONFIG`. The original public baseline preserved scientific ASTs through path changes. This CORR01 successor additionally corrects the HRS 2018 recognition mapping; other scientific logic is unchanged. A primary-label reproduction adapter retains the primary source functions and excludes historical non-production branches. This publication task performed structural checks only; no scientific pipeline was executed.

## Reproducing figures/tables
After an authorized local reproduction, use the generated aggregate outputs:
```sh
python code/figures/build_figures.py --source "$PROJECT_ROOT/analysis/LABELBIAS_PROD01" --output output/figures
python code/figures/calibration_display.py --source "$PROJECT_ROOT/analysis/LABELBIAS_PROD01/03_aim3/PROD01_AIM3_CALIBRATION.csv" --output output/calibration
```
An authorized CHARLS user can additionally supply `--private-charls-oof` to reconstruct the original Figure 4B density panel locally. Without that file the script explicitly displays controlled-access unavailability; it does not invent individual risks. Never distribute the prediction file. Tables use the locally generated Aim 1/2/3 aggregate CSVs; manuscript layout, author metadata, private audits and historical candidate-table assemblers are excluded.

## Main scientific boundaries
- M is not biological ground truth; R is not diagnostic error.
- Recognition associations are observational and do not establish causal access effects.
- The six primary CHARLS comparisons did not support the hypothesized greater education/contact incremental contribution for R than M. The corrected HRS education-mappable external comparison is SECONDARY_SUPPORTED_WITH_QUALIFICATIONS; it is not primary confirmation, causal evidence, or cross-cohort replication.
- Similar overall ranking can coexist with partially different high-risk membership; this does not establish clinical utility or fairness.
- CHARLS development and ELSA/HRS external prediction horizons differ; external transport is qualified.
- A lower BP threshold was planned but not part of the frozen production analysis and was not executed in that analysis.
- Calibration interval provenance does not establish coverage or explain a bootstrap distribution shift.

## HRS CORR01 successor
The original public baseline is [eb3ac6a](https://github.com/woshizh321/hypertension-target-definition/commit/eb3ac6aaf30797865bd3a31a851a0f4d40c91bcf). This successor follows a PI-authorized, independently audited post-lock data-integrity correction. HRS 2014 OC005 remains 1/3 positive and 4/5 negative. HRS 2018 QC005 uses 1/6 positive and 4/5 negative; code 3 and other unsupported or missing responses remain unknown. Code 6 retains historical professional recognition and requires neither current BP elevation nor current treatment, QC006=6, or QZ101=1. See [source definitions](documentation/VARIABLE_DEFINITIONS.md). The baseline commit remains the original release; this branch is the corrected implementation pending independent code audit and PI release authorization, without a new release tag.

## Software environment
Recorded Python/package versions are in [environment/](environment/). Run the dependency-free structural checks with `python tests/test_public_structure.py`. End-to-end numerical equivalence has not been demonstrated for the public portability adapters; validate acquired release identities, datatype preservation, native keys and local output hashes before interpretation.

## Citation
Please cite the accompanying manuscript when available. Author metadata remain unconfirmed; CITATION.cff is temporarily omitted because its author requirements cannot be met without inventing names. Repository: https://github.com/woshizh321/hypertension-target-definition. No manuscript or software DOI has been created.

## License
The repository's original project code is released under the MIT License. Third-party libraries retain their own licenses. This license grants no rights to any source dataset, provider documentation, private contract or independently acquired output.

## Data-use notice
The absence of data from this repository is intentional. Aggregate datasets are also excluded because code publication does not establish their redistribution permissions. Do not upload restricted source data or individual outputs to this repository, issues, pull requests or AI services. See [DATA_ACCESS.md](DATA_ACCESS.md).
