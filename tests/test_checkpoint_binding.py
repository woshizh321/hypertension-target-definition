"""Synthetic fixtures only: no real checkpoint, prediction or model fit."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('checkpoint_binding',ROOT/'code/analysis/checkpoint_binding.py')
cb=importlib.util.module_from_spec(spec);spec.loader.exec_module(cb)

def fake_payload(count=200):
    p={'completed':count,'RNG':np.random.PCG64(42).state,
       'bootlog':[{'bootstrap':b,'status':'PASS'} for b in range(count)]}
    for name,n in cb.ROWS_PER_REPLICATE.items():
        p[name]=[{'bootstrap':b,'synthetic':0} for b in range(count) for _ in range(n)]
    return p

class CheckpointBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'synthetic.joblib'
        self.identity={'schema':cb.SCHEMA,'science':cb.SCIENCE,
                       'inputs':{'CHARLS':'synthetic-c','ELSA':'synthetic-e','HRS':'synthetic-h'},
                       'hrs_common_n':1623,'hrs_ordered_id_targets_sha256':'synthetic-ordered-targets',
                       'scientific_source_sha256':{'model':'synthetic-model'}}
        self.payload=fake_payload()
    def write(self):cb.write_bound_checkpoint(self.path,self.payload,self.identity)
    def test_matching_fixture_accepted(self):
        self.write();result=cb.load_bound_checkpoint(self.path,self.identity)
        self.assertEqual(result['completed'],200);self.assertEqual(result['provenance'],self.identity)
    def test_missing_or_legacy_binding_rejected_before_deserialization(self):
        self.path.write_bytes(b'untrusted synthetic bytes')
        with patch.object(cb.joblib,'load',side_effect=AssertionError('unsafe load')):
            with self.assertRaises(cb.CheckpointBindingError):cb.load_bound_checkpoint(self.path,self.identity)
    def test_pre_corr01_identity_rejected(self):
        self.write();now=copy.deepcopy(self.identity);now['hrs_common_n']=1619
        with self.assertRaises(cb.CheckpointBindingError):cb.load_bound_checkpoint(self.path,now)
    def test_same_n_different_target_identity_rejected(self):
        self.write();now=copy.deepcopy(self.identity);now['hrs_ordered_id_targets_sha256']='different-targets'
        with self.assertRaises(cb.CheckpointBindingError):cb.load_bound_checkpoint(self.path,now)
    def test_each_dataset_input_mismatch_rejected(self):
        self.write()
        for ds in ('CHARLS','ELSA','HRS'):
            now=copy.deepcopy(self.identity);now['inputs'][ds]='different'
            with self.subTest(dataset=ds), self.assertRaises(cb.CheckpointBindingError):
                cb.load_bound_checkpoint(self.path,now)
    def test_different_specification_rejected(self):
        self.write();now=copy.deepcopy(self.identity);now['scientific_source_sha256']['model']='changed'
        with self.assertRaises(cb.CheckpointBindingError):cb.load_bound_checkpoint(self.path,now)
    def test_immutable_identity_record_cannot_be_rebound(self):
        self.write();now=copy.deepcopy(self.identity);now['inputs']['HRS']='different'
        with self.assertRaises(cb.CheckpointBindingError):cb.write_bound_checkpoint(self.path,self.payload,now)
        self.assertEqual(cb.load_bound_checkpoint(self.path,self.identity)['completed'],200)
    def test_incomplete_checkpoint_rejected(self):
        cb.write_bound_checkpoint(self.path,fake_payload(25),self.identity)
        with self.assertRaises(cb.CheckpointBindingError):cb.load_bound_checkpoint(self.path,self.identity)
    def test_inconsistent_metadata_and_bytes_rejected(self):
        self.write();side=Path(str(self.path)+'.provenance.json');m=json.loads(side.read_text())
        m['RNG']['state']['state']+=1;side.write_text(json.dumps(m))
        with self.assertRaises(cb.CheckpointBindingError):cb.load_bound_checkpoint(self.path,self.identity)
        self.write();self.path.write_bytes(self.path.read_bytes()+b'x')
        with patch.object(cb.joblib,'load',side_effect=AssertionError('unsafe load')):
            with self.assertRaises(cb.CheckpointBindingError):cb.load_bound_checkpoint(self.path,self.identity)
    def test_missing_or_truncated_collection_rejected(self):
        self.payload['Bext'].pop()
        with self.assertRaises(cb.CheckpointBindingError):self.write()
    def test_explicit_checks_survive_optimized_python(self):
        self.write();now=copy.deepcopy(self.identity);now['inputs']['HRS']='changed'
        code=('import importlib.util,json,sys; '
              's=importlib.util.spec_from_file_location("cb",sys.argv[1]); '
              'm=importlib.util.module_from_spec(s);s.loader.exec_module(m); '
              'm.load_bound_checkpoint(sys.argv[2],json.loads(sys.argv[3]))')
        proc=subprocess.run([sys.executable,'-O','-c',code,str(ROOT/'code/analysis/checkpoint_binding.py'),
                             str(self.path),json.dumps(now)],capture_output=True,text=True)
        self.assertNotEqual(proc.returncode,0);self.assertIn('CheckpointBindingError',proc.stderr)
    def test_writer_reader_wiring_and_no_other_checkpoint_loader(self):
        prediction=(ROOT/'code/analysis/03_aim3_prediction.py').read_text()
        recovery=(ROOT/'code/analysis/03b_serialization_recovery.py').read_text()
        self.assertEqual(prediction.count('write_bound_checkpoint('),1)
        self.assertEqual(recovery.count('load_bound_checkpoint('),1)
        self.assertLess(recovery.index('load_bound_checkpoint('),recovery.index('exec(compile(prefix'))
        self.assertNotIn("joblib.load(O/'03_aim3/PROD01_BOOTSTRAP_CHECKPOINT",recovery)
        for f in (ROOT/'code').rglob('*.py'):
            if f.name in ('03_aim3_prediction.py','03b_serialization_recovery.py'):continue
            self.assertNotIn('PROD01_BOOTSTRAP_CHECKPOINT.joblib',f.read_text(),str(f))
    def test_actual_hrs_size_guard_at_normal_and_optimized_levels(self):
        tree=ast.parse((ROOT/'code/analysis/03_aim3_prediction.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.If) and 'len(D[d])' in ast.unparse(n.test)]
        self.assertEqual(len(nodes),1)
        for opt in (0,2):
            guard=compile(ast.Module(body=nodes,type_ignores=[]),'guard','exec',optimize=opt)
            exec(guard,{'D':{'CHARLS':range(5303),'ELSA':range(2075),'HRS':range(1623)}})
            with self.assertRaises(AssertionError):
                exec(guard,{'D':{'CHARLS':range(5303),'ELSA':range(2075),'HRS':range(1619)}})
    def test_authoritative_ordered_identity_changes_on_target_or_order(self):
        z=pd.DataFrame({'id':[f'fixture-{i}' for i in range(1623)],'M1':[0]*1623,
                        'R1':[0]*1623,'aim3_common':[True]*1623})
        h=cb.hrs_fingerprint(z);q=z.copy();q.loc[0,'R1']=1
        self.assertNotEqual(h,cb.hrs_fingerprint(q));self.assertNotEqual(h,cb.hrs_fingerprint(z.iloc[::-1]))
        with self.assertRaises(cb.CheckpointBindingError):cb.hrs_fingerprint(z.iloc[:-1])
    def test_current_identity_binds_real_synthetic_files_and_lock(self):
        fixture=Path(self.tmp.name);project=fixture/'project';repo=fixture/'repo'
        root=project/'analysis/LABELBIAS_PROD01';(root/'00_lock').mkdir(parents=True)
        (root/'08_analytic_inputs').mkdir();(root/'03_aim3').mkdir()
        files=set(cb.AUTHORITY)|{'code/analysis/03_aim3_prediction.py','code/analysis/03b_serialization_recovery.py',
              'code/analysis/checkpoint_binding.py','code/analysis/prod01_common.py',
              'code/analysis/00_prepare_blind_inputs.py','code/analysis/01_freeze_analysis.py'}
        for name in files:
            target=repo/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        hrs=pd.DataFrame({'id':[f'fixture-{i}' for i in range(1623)],'M1':[0]*1623,
                          'R1':[0]*1623,'aim3_common':[True]*1623})
        samples=[]
        for ds in ('CHARLS','ELSA','HRS'):
            path=root/'08_analytic_inputs'/f'BASELINE_LABEL_PREDICTORS_{ds}.parquet'
            (hrs if ds=='HRS' else hrs.iloc[:2]).to_parquet(path,index=False)
            samples.append({'dataset':ds,'aim':'AIM3_COMMON','analytic_file_sha256':cb.file_sha(path)})
        lock=root/'00_lock/PROD01_ANALYSIS_LOCK.json';lock.write_text(json.dumps({'samples':samples}))
        (root/'00_lock/PROD01_ANALYSIS_LOCK_SHA256.txt').write_text(cb.file_sha(lock)+'  '+lock.name+'\n')
        for name in ('PROD01_CHARLS_OOF_PREDICTIONS.parquet','PROD01_PAIRED_FOLD_ASSIGNMENTS.csv',
                     'PROD01_CHARLS_FROZEN_MODELS.joblib'):(root/'03_aim3'/name).write_text('synthetic')
        fake_authority={s['dataset']:s['analytic_file_sha256'] for s in samples}
        with patch.object(cb,'HRS_ID_TARGETS_SHA256',cb.hrs_fingerprint(hrs)), patch.object(cb,'INPUT_AUTHORITY',fake_authority):
            ident=cb.current_identity(project,repo)
            self.assertEqual(ident['hrs_common_n'],1623)
            (root/'03_aim3/PROD01_PAIRED_FOLD_ASSIGNMENTS.csv').write_text('changed')
            self.assertNotEqual(ident,cb.current_identity(project,repo))
            hrs.loc[0,'R1']=1
            hrs.to_parquet(root/'08_analytic_inputs/BASELINE_LABEL_PREDICTORS_HRS.parquet',index=False)
            samples[2]['analytic_file_sha256']=cb.file_sha(root/'08_analytic_inputs/BASELINE_LABEL_PREDICTORS_HRS.parquet')
            fake_authority['HRS']=samples[2]['analytic_file_sha256']
            lock.write_text(json.dumps({'samples':samples}))
            (root/'00_lock/PROD01_ANALYSIS_LOCK_SHA256.txt').write_text(cb.file_sha(lock)+'  '+lock.name+'\n')
            with self.assertRaises(cb.CheckpointBindingError):cb.current_identity(project,repo)

if __name__=='__main__':unittest.main()
