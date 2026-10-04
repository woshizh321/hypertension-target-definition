# Frozen design summary

CHARLS 2013–2015 is the development/discovery transition; ELSA W4–W6 and HRS 2014–2018 provide qualified external evaluation; NHANES 2015–2016 is cross-sectional only. Native person identifiers link within each study; there is no cross-study person linkage.

Aim 1 describes complete observed M/R states in valid-label positive-weight domains, with unresolved observation fractions kept separate. CHARLS/ELSA design intervals are not replaced with naive bootstrap population intervals. HRS/NHANES retain their native survey designs.

Aim 2 uses baseline M+/R− independently of T; recognition requires valid nonproxy follow-up R. Cohort-specific binomial-logit associations use fixed core adjustment, source-specific robust variance and marginal standardization. Education is the sole BASE_SES domain; contact/access constructs remain source-native. These are observed-follow-up conditional associations, not causal effects.

Aim 3 uses baseline M−/R− and common valid nonproxy follow-up M/R, independently of T. Paired ridge models hold participants, predictor information, folds and preprocessing constant. Five grouped folds, two repeats, fixed C=1, training-only preprocessing and full-pipeline paired cluster-bootstrap procedures are retained exactly. CHARLS trains models; ELSA/HRS apply unchanged models, without recalibration. Access/FULL transport is not estimable because the source constructs cannot be defensibly mapped.

Risk-tail membership uses a fixed capacity and deterministic native-key tie-breaking. It does not adjudicate clinical need, diagnostic error, fairness or benefit. The primary education/contact increment finding remains negative; mixed evidence is preserved. No new science or reinterpretation was performed for publication.
