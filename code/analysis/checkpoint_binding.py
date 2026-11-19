"""Bind trusted local recovery checkpoints to their exact scientific context.

The JSON sidecar is checked before deserialization. It detects accidental
cross-version reuse, not a malicious actor able to alter both local files.
Only deserialize trusted, owner-controlled local checkpoint artifacts.
"""
import hashlib
import importlib.metadata
import io
import json
import os
import platform
from pathlib import Path
import tempfile
from collections import Counter

import joblib
import numpy as np
import pandas as pd

SCHEMA = 'labelbias-bootstrap-checkpoint-v1'
SCIENCE = 'LABELBIAS-PROD01-HRS-CORR01'
HRS_ID_TARGETS_SHA256 = '8662366e20268838136cc6babc8208c59cbe2a22a9496e01a659e8433662b299'
INPUT_AUTHORITY = {
    'CHARLS': '644f3d8bf5b33bffb6f0d8462728fb37f12a520af989be0d2e54c5aff7d6be2a',
    'ELSA': 'b13d7412497576405ca8d9a56a84091ac0c6529c64477612d083e477ec3ce459',
    'HRS': 'dafb60739fd89155e4543eab0882f84577935b6dda3f4123d2889744bfa66ab4',
}
AUTHORITY = {
    'code/label_derivation/hrs_recognition.py': 'da659e7f13417fd2e2bc1f24a97a28c4e99e86e7b7421c0ead1d4750b1d05be5',
    'code/label_derivation/02_construct_primary_labels.py': 'f954e30f31a379ecfbb4e6b1e2df9bd2782f50952be4fb9d943a1a484157348a',
    'documentation/primary_label_contract.json': 'd70b116fda54e5638b48d5520a98242506a4e6b6de43987e99e30b2112d8be8e',
}
COLLECTIONS = ('Bmain','Binc','Brank','Bcal','Bsub','Bext','Bextinc',
               'Bextrank','Bextcal','Bextsub')
ROWS_PER_REPLICATE = dict(Bmain=48,Binc=36,Brank=22,Bcal=48,Bsub=56,
                          Bext=72,Bextinc=24,Bextrank=44,Bextcal=72,Bextsub=112)

class CheckpointBindingError(RuntimeError):
    """Missing, inconsistent or incompatible recovery provenance."""

def _require(condition, message):
    if not condition:
        raise CheckpointBindingError(message)

def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()

def hrs_fingerprint(frame):
    """SHA-256 of ordered JSON [native-id, binary M1, binary R1] lines."""
    d=frame.loc[frame['aim3_common']]
    _require(len(d)==1623 and d.id.notna().all() and d.id.astype(str).is_unique,
             'HRS cohort identity is invalid')
    _require(d[['M1','R1']].isin([0,1]).all().all(), 'HRS targets not binary')
    h=hashlib.sha256()
    for identity,m,r in zip(d.id.astype(str),d.M1,d.R1):
        h.update((json.dumps([identity,int(m),int(r)],ensure_ascii=True,
                             separators=(',',':'))+'\n').encode('utf-8'))
    return h.hexdigest()

def _verify_scientific_inputs(project_root, repository_root):
    root=Path(project_root)/'analysis/LABELBIAS_PROD01'
    repo=Path(repository_root)
    lock=root/'00_lock/PROD01_ANALYSIS_LOCK.json'
    lock_hash=file_sha(lock)
    lock_text=(root/'00_lock/PROD01_ANALYSIS_LOCK_SHA256.txt').read_text()
    _require(lock_hash+'  '+lock.name in lock_text, 'Analysis lock hash mismatch')
    lockdata=json.loads(lock.read_text())
    inputs={}
    for dataset in ('CHARLS','ELSA','HRS'):
        p=root/'08_analytic_inputs'/f'BASELINE_LABEL_PREDICTORS_{dataset}.parquet'
        digest=file_sha(p)
        _require(digest==INPUT_AUTHORITY[dataset], dataset+' input differs from frozen authority')
        matches=[s for s in lockdata['samples'] if s['dataset']==dataset and s['aim']=='AIM3_COMMON']
        _require(len(matches)==1 and matches[0]['analytic_file_sha256']==digest,
                 dataset+' input does not match current lock')
        inputs[dataset]=digest
    hrs=pd.read_parquet(root/'08_analytic_inputs/BASELINE_LABEL_PREDICTORS_HRS.parquet',
                        columns=['id','aim3_common','M1','R1'])
    identity=hrs_fingerprint(hrs)
    _require(identity==HRS_ID_TARGETS_SHA256, 'HRS cohort does not match CORR01 authority')
    for path,digest in AUTHORITY.items():
        _require(file_sha(repo/path)==digest, 'HRS mapping authority mismatch: '+path)
    return root,repo,lock_hash,inputs,identity

def verify_scientific_inputs(project_root, repository_root):
    """Reject non-authoritative inputs before model execution."""
    try:
        return _verify_scientific_inputs(project_root,repository_root)
    except CheckpointBindingError:
        raise
    except (OSError,ValueError,TypeError,KeyError,IndexError) as e:
        raise CheckpointBindingError('Cannot establish current scientific identity') from e

def _current_identity(project_root, repository_root):
    """Independently derive current identities; no model fitting or prediction."""
    root,repo,lock_hash,inputs,identity=verify_scientific_inputs(project_root,repository_root)
    spec_files=('code/analysis/03_aim3_prediction.py','code/analysis/03b_serialization_recovery.py',
                'code/analysis/checkpoint_binding.py','code/analysis/prod01_common.py',
                'code/analysis/00_prepare_blind_inputs.py','code/analysis/01_freeze_analysis.py')
    saved=('PROD01_CHARLS_OOF_PREDICTIONS.parquet','PROD01_PAIRED_FOLD_ASSIGNMENTS.csv',
           'PROD01_CHARLS_FROZEN_MODELS.joblib')
    return {'schema':SCHEMA,'science':SCIENCE,'input_sha256':inputs,
            'analysis_lock_sha256':lock_hash,'hrs_common_n':1623,
            'hrs_ordered_id_targets_sha256':identity,'hrs_mapping_sha256':dict(AUTHORITY),
            'scientific_source_sha256':{s:file_sha(repo/s) for s in spec_files},
            'recovery_dependencies_sha256':{s:file_sha(root/'03_aim3'/s) for s in saved},
            'software':{p:importlib.metadata.version(p) for p in
                        ('numpy','pandas','scipy','scikit-learn','statsmodels','joblib')},
            'python':platform.python_version(),
            'threads':{k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS')}}

def current_identity(project_root, repository_root):
    try:
        return _current_identity(project_root,repository_root)
    except CheckpointBindingError:
        raise
    except (OSError,ValueError,TypeError,KeyError,IndexError) as e:
        raise CheckpointBindingError('Cannot establish current scientific identity') from e

def _validate_payload(payload, complete_required):
    _require(isinstance(payload,dict), 'Checkpoint is not a mapping')
    count=payload.get('completed')
    _require(type(count) is int and 1<=count<=200 and (not complete_required or count==200),
             'Invalid or incomplete bootstrap iteration count')
    rng=payload.get('RNG')
    try:
        _require(isinstance(rng,dict) and rng.get('bit_generator')=='PCG64','Invalid RNG state')
        generator=np.random.PCG64();generator.state=rng
    except (ValueError,TypeError,KeyError) as e:
        raise CheckpointBindingError('Invalid RNG state') from e
    log=payload.get('bootlog')
    _require(isinstance(log,list) and len(log)==count and all(isinstance(row,dict) for row in log) and
             [row.get('bootstrap') for row in log]==list(range(count)) and
             all(row.get('status')=='PASS' for row in log), 'Invalid bootstrap log')
    for name in COLLECTIONS:
        rows=payload.get(name)
        _require(isinstance(rows,list) and rows and all(isinstance(row,dict) for row in rows),
                 'Missing bootstrap collection: '+name)
        _require({row.get('bootstrap') for row in rows}==set(range(count)),
                 'Incomplete bootstrap collection: '+name)
        _require(Counter(row.get('bootstrap') for row in rows)==
                 {b:ROWS_PER_REPLICATE[name] for b in range(count)},
                 'Wrong per-replicate record counts: '+name)

def _write_atomic(path, data):
    path=Path(path)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def _identity_record(path, identity, create):
    """Create one immutable identity record for this checkpoint series."""
    record=Path(str(path)+'.identity.json')
    expected={'schema':SCHEMA,'identity':identity}
    if create:
        try:
            fd=os.open(record,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd,'w') as f:
                json.dump(expected,f,sort_keys=True,separators=(',',':'))
                f.flush();os.fsync(f.fileno())
    _require(record.is_file(),'Missing immutable checkpoint identity')
    try:
        stored=json.loads(record.read_text())
    except (OSError,ValueError) as e:
        raise CheckpointBindingError('Invalid immutable checkpoint identity') from e
    _require(stored==expected,'Immutable checkpoint identity mismatch')

def write_bound_checkpoint(path, payload, identity):
    """Persist payload plus non-secret sidecar; mismatched partial writes fail closed."""
    _validate_payload(payload,False)
    _identity_record(path,identity,True)
    envelope=dict(payload,provenance=identity)
    stream=io.BytesIO();joblib.dump(envelope,stream,compress=3);raw=stream.getvalue()
    metadata={'schema':SCHEMA,'identity':identity,'completed':payload['completed'],
              'RNG':payload['RNG'],'checkpoint_sha256':hashlib.sha256(raw).hexdigest()}
    _write_atomic(path,raw)
    _write_atomic(str(path)+'.provenance.json',
                  json.dumps(metadata,sort_keys=True,separators=(',',':')).encode())

def load_bound_checkpoint(path, expected_identity):
    """Verify sidecar/bytes before trusted local deserialization, then payload."""
    path=Path(path); side=Path(str(path)+'.provenance.json')
    _require(side.is_file(), 'Missing provenance: legacy checkpoint cannot be recovered')
    _identity_record(path,expected_identity,False)
    try:
        meta=json.loads(side.read_text())
    except (OSError,ValueError) as e:
        raise CheckpointBindingError('Invalid checkpoint provenance') from e
    _require(isinstance(meta,dict) and set(meta)=={'schema','identity','completed','RNG','checkpoint_sha256'},
             'Incomplete checkpoint provenance')
    _require(meta['schema']==SCHEMA and meta['identity']==expected_identity,
             'Checkpoint does not match current scientific identity')
    _require(type(meta['completed']) is int and meta['completed']==200,
             'Checkpoint is not complete')
    try:
        raw=path.read_bytes()
    except OSError as e:
        raise CheckpointBindingError('Checkpoint file unavailable') from e
    _require(hashlib.sha256(raw).hexdigest()==meta['checkpoint_sha256'],
             'Checkpoint bytes do not match provenance')
    try:
        payload=joblib.load(io.BytesIO(raw))  # only trusted local files; not safe for untrusted pickle
    except Exception as e:
        raise CheckpointBindingError('Invalid trusted checkpoint payload') from e
    _require(isinstance(payload,dict) and payload.get('provenance')==expected_identity,
             'Embedded checkpoint identity mismatch')
    _require(set(payload)=={'completed','RNG','bootlog','provenance',*COLLECTIONS},
             'Unexpected checkpoint fields')
    _require(payload.get('completed')==meta['completed'] and payload.get('RNG')==meta['RNG'],
             'Checkpoint completion or RNG metadata mismatch')
    _validate_payload(payload,True)
    return payload
