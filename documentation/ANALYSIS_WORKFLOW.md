# Authorized local reproduction workflow

The publication task did not execute these scientific commands. Run them yourself only after obtaining source access and verifying the required interfaces in DATA_ACCESS.md. Use a fresh workspace; original locks/data must never be overwritten.

```sh
python -m pip install -r environment/requirements.txt
export DATA_ROOT=/path/to/independently-acquired-data
export PROJECT_ROOT=/path/to/new-private-reproduction-workspace
export SOURCE_CONFIG=/path/to/private-source-paths.json
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
python code/label_derivation/02_construct_primary_labels.py
python code/analysis/00_prepare_blind_inputs.py
python code/analysis/01_freeze_analysis.py
python code/analysis/02_aim1_aim2.py
python code/analysis/03_aim3_prediction.py
```

The `reproduction_authorization` configuration must point to your own local reproduction authorization record under DATA_ROOT. It is a provenance input, not the original PI task. Public reproduction locks/hashes identify your new workspace and do not replace the original study's lock identity or establish prospective prespecification.

## Production export recovery
The original prediction run completed 200 full refits and then failed during Parquet serialization of mixed rank-fraction types. `03b_serialization_recovery.py` was the executed completion step. If the same export error occurs **after a completed checkpoint**, run:
```sh
python code/analysis/03b_serialization_recovery.py
```
Never relaunch the model/200-refit job simply to repair serialization. Recovery reuses the completed checkpoint, preserves primary numbers and reaches the locked missing-information sensitivity; it is not a bootstrap shortcut. If the original script finishes without that error, recovery is unnecessary.

## Correspondence with original execution
|Public file|Executed source correspondence|
|---|---|
|02_construct_primary_labels.py|Primary functions and source-spine loop from 02_construct_and_count.py; historical alternate-threshold and strict-T event branches excluded. Adapter creates private primary interfaces and treatment context only. CORR01 successor applies the PI-locked HRS 2018 recognition mapping through hrs_recognition.py; HRS 2014 is unchanged.|
|00_prepare_blind_inputs.py|Current source-closure-corrected preparation, same name; paths only changed.|
|01_freeze_analysis.py|Current lock writer, same name; paths only changed.|
|02_aim1_aim2.py|Final role-metadata-corrected version; no numerical repair; paths only changed.|
|03_aim3_prediction.py|Executed 200-refit paired prediction procedure, same name.|
|03b_serialization_recovery.py|Executed checkpoint-completion procedure, same name.|
|prod01_common.py|Executed helper, same name; paths only changed.|
|code/figures/*.py|Byte-identical final manuscript figure/calibration presentation code.|

Private audit/report writers, original metadata scraping, historical repair scripts, PRE_REPAIR variants and obsolete candidate-figure/table generators are excluded. No entire private history is imported. The original baseline primary adapter preserved all retained scientific function ASTs; the only removed BP assignment was the non-production alternate-threshold variable. The CORR01 successor changes only the HRS 2018 R mapping and delegates it to a side-effect-free helper; no other source, eligibility, treatment, BP, model or validation rule is changed. Its added manifest/configuration scaffolding does not claim to be the original execution history.

## Outputs and verification
Aim 1/2/3 machine-readable CSVs are written under PROJECT_ROOT/analysis/LABELBIAS_PROD01. Manuscript table source columns are those CSVs; final Word layout is an editorial artifact excluded here. Figure generation reads these outputs without fitting. The finalized coefficient values can be exported from the saved local frozen models using their feature-name order; they are not public fitted models. Preserve source hashes, native-key uniqueness, all denominators, fold membership and output comparisons locally. The production sample-size guards remain unchanged; a different release/sample should fail rather than silently create an alternative study.
