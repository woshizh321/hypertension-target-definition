"""HRS recognition mapping only; no source reads or pipeline execution.

CORR01 preserves historical recognition in 2018 QC005 code 6.
The wave and source-field guard matches the PI-locked audited correction.
"""
import pandas as pd


def map_hrs_recognition(values, wave, recognition_fields):
    """Return R (1/0/NaN), preserving unsupported and missing responses.

    HRS 2014 OC005: 1/3 positive, 4/5 negative.
    HRS 2018 QC005: 1/6 positive, 4/5 negative; 3 unsupported.
    No treatment, preload, BP, or future information is consulted.
    """
    mapping = (
        {1: 1.0, 6: 1.0, 4: 0.0, 5: 0.0}
        if wave == '2018' and recognition_fields == ['QC005']
        else {1: 1.0, 3: 1.0, 4: 0.0, 5: 0.0}
    )
    return pd.to_numeric(values, errors='coerce').map(mapping)
