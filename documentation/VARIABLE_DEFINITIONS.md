# Variable definitions and source mapping

M: source-specific current measurement phenotype, mean SBP >=140 or DBP >=90 mmHg, independent of medication/recognition. Normally at least two valid paired readings are required. ELSA W4 uses its official second/third-reading rule after complete validity flags; W6 retains complete-pair and rest-context rules. NHANES retains valid same-visit attempts including a fourth attempt, source even-value/range rules and permitted DBP zero. Missing/routed readings are not numeric zeros. See primary_label_contract.json and the retained primary functions.

R: native professional-recognition response, with source confirmation/dispute/retraction rules preserved. Neither missing responses nor generic self-recognition create R. T: explicit current BP-treatment response; unknown/skip is distinct from untreated. T does not constrain production Aim 2/3 eligibility.

|Study|Recognition / treatment|Baseline predictors|
|---|---|---|
|CHARLS|da007 doctor-history/confirmation/update routes; da011 treatment slots|Birth-year confirmation routes; ba000_w2_3/xrgender sex; bd001/update/confirmed preload education; ed001 last-month contact|
|ELSA|hedawbp/hedacbp/hedanbp and hediabp/hedimbp recognition with explicit-none/retraction rules; hemda/hemdab treatment|indager; indsex; edqual LOW/HIGH/FOREIGN_OTHER; scedgp EASY/DIFFICULT/PREFERENCE_NOT_TO_GO|
|HRS|OC005/QC005 recognition, OC006/QC006 treatment|OA019; OX060_R baseline sex; OB014 then OZ216 education; ON147 contact, ON290 secondary affordability component|
|NHANES|BPQ020 recognition; BPQ050A explicit current treatment|RIDAGEYR questionnaire eligibility; BPX readings; WTMEC2YR, SDMVSTRA/SDMVPSU design|

## HRS wave-specific recognition (CORR01)
HRS 2014 OC005: 1/3 -> R+, 4/5 -> R-. HRS 2018 QC005: 1/6 -> R+, 4/5 -> R-; code 3 is unsupported and remains unknown, as do other unsupported or missing responses. QC005=6 retains historical professional recognition; it does not establish current disease, current treatment, or incident diagnosis timing. Classification uses QC005 alone, without requiring QC006=6, QZ101=1, or elevated BP. The existing R-status labels and dispute/retraction flag for codes 3/4 are preserved exactly as audited; that flag is separate from R and is not a positivity or eligibility rule. T remains based on the native treatment field.

Source context: [official HRS 2018 C-module codebook](https://hrs.isr.umich.edu/sites/default/files/meta/2018/core/codebook/h18c_r.htm) and [official questionnaire](https://hrs.isr.umich.edu/sites/default/files/meta/2018/core/qnaire/online/03hr18C.pdf). No licensed source material is reproduced here. This source-specific correction is PI-authorized and independently audited, not an endpoint redefinition.

BASE: age, sex, SBP and DBP. BASE_SES adds education only. BASE_ACCESS adds native contact/access; FULL adds both domains. No income/wealth proxy is introduced. Source ID variable names appear only in executable joins and method schemas; no identifier values are provided.

Numeric age missingness receives train-fold median and an explicit indicator in prediction; category unknowns remain explicit. No outcome imputation. Follow-up death, nonresponse, proxy-only and unknown observation are not negative events. Within-wave physical and interview timestamps are not assumed identical; external horizons remain qualified.
