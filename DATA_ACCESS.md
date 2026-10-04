# Data access and controlled interfaces

Acquire CHARLS, ELSA, HRS and NHANES independently from their original providers through the links in README. Check current access terms, release citations and licensing yourself. No participant files, individual derived records, OOF predictions, source codebooks or manuscript aggregate datasets are distributed here. Permission for aggregate redistribution is not inferred. The MIT code license does not apply to source data.

## Local interfaces
Copy `documentation/source_paths.example.json` outside the repository and set `SOURCE_CONFIG` to that private copy. Values are relative to `DATA_ROOT`, or may be absolute in the private copy. Use a fresh `PROJECT_ROOT`. Preserve all source column names, codes, variable types, missing-value semantics, person grain and release identities. Do not modify the frozen wave pairs to make a reproduction fit.

- CHARLS 2013/2015: native Health_Status_and_Functioning.dta, Biomarker.dta and Weights.dta; 2015 Sample_Infor.dta. Baseline predictors additionally use Demographic_Background.dta and Health_Care_and_Insurance.dta.
- ELSA W4/W6: loss-preserving MAIN_INTERVIEW and NURSE parquet interfaces. W4 predictors additionally require DERIVED education. The predictor directory must have `module=MAIN_INTERVIEW/<release>/data.parquet` and `module=DERIVED/<release>/data.parquet`. Acquire releases through ELSA/UK Data Service and construct these interfaces locally. Do not substitute a harmonized measurement or change native negative codes; retain missing values and variable case. This repository does not distribute the source curator's registry or licensed dictionary.
- HRS native 2014/2018 core ZIP packages: retain nested sta.zip and da.zip module structures and native dictionary columns. Tracker trk2022v1.zip supplies design/physical-weight and documented history fields; it never changes baseline membership. Native baseline fields supply education and sex; later tracker sex is not a predictor.
- NHANES 2015–2016: a local DuckDB view named `release_2015_2016_v1`, joined one-to-one by SEQN from the authorized BPX_I, BPQ_I and DEMO_I releases. Retain the full MEC-weight design universe before selecting the questionnaire age domain. Required fields are listed in primary_label_contract.json. No cross-cycle linkage or pooling.

Source interfaces must be verified locally against their provider dictionaries and immutable source hashes. The configured path template is a schema/configuration asset, not a source-data release. Numeric missing-code keys are method definitions, not participant observations. The public adapters are structurally checked and have not been executed against source rows in this release task. A successful syntax check does not establish equivalence of a newly constructed source interface.

## HRS and AI/data-use boundary
No HRS participant material or individual derived output is public. The saved project policy record was dated 2026-08-04; licensed processing must follow applicable provider AI/data-use restrictions. Do not expose source microdata or individual derivatives to LLM tools or indexed AI workspaces. Historical handling remains a separate PI determination; this code publication does not certify it.

## Local outputs
Code writes private label files, analytic inputs, folds, predictions, fitted models and bootstrap checkpoints under PROJECT_ROOT. They are needed only for authorized local reproduction and must never be committed. Public source-data, aggregate-example and model directories are deliberately absent. Review any independently produced aggregates for rights before redistribution.
