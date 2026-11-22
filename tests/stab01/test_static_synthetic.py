"""Synthetic-only tests. Never loads study data or fits an estimator."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import warnings
from sklearn.exceptions import ConvergenceWarning

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'code/stab01/stab01_execution.py'
TREE=ast.parse(SRC.read_text())
MAIN=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='main')

def get_statement(line):
 return next(n for n in ast.walk(MAIN) if getattr(n,'lineno',None)==line)

def run_fragment(start,end,variables):
 nodes=[n for n in ast.walk(MAIN) if hasattr(n,'lineno') and n.lineno>=start and n.end_lineno<=end and isinstance(n,ast.stmt)]
 # Select outer statements only.
 nodes=[n for n in nodes if not any(p is not n and p.lineno<=n.lineno and p.end_lineno>=n.end_lineno for p in nodes)]
 nodes.sort(key=lambda x:x.lineno)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),'synthetic','exec'),variables)

class Tests(unittest.TestCase):
 def test_import_is_inert(self):
  code="import runpy,sys;runpy.run_path(sys.argv[1],run_name='probe')"
  env=dict(os.environ);env.pop('STAB01_RUN_AUTHORIZED',None)
  p=subprocess.run([sys.executable,'-c',code,str(SRC)],env=env,capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr)
 def test_explicit_authorization_required(self):
  env=dict(os.environ);env.pop('STAB01_RUN_AUTHORIZED',None);env.pop('STAB01_PRIVATE_INPUT_MANIFEST',None)
  p=subprocess.run([sys.executable,str(SRC)],env=env,capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('authorization is required',p.stderr)
 def test_optimized_mode_rejected(self):
  p=subprocess.run([sys.executable,'-O',str(SRC)],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('Optimized Python is unsupported',p.stderr)
 def test_fit_rejects_single_class_and_nonfinite(self):
  node=next(n for n in MAIN.body if isinstance(n,ast.FunctionDef) and n.name=='fit')
  def gate(ok,msg):
   if not ok:raise AssertionError(msg)
  class Model:
   def predict_proba(self,x):return np.array([[.2,.8],[.1,float('nan')]])
  ctx={'gate':gate,'warnings':warnings,'ConvergenceWarning':ConvergenceWarning,'pairedfit':lambda a,b:{'M':Model(),'R':Model()},'Xframe':lambda d:d,'np':np}
  exec(compile(ast.Module(body=[node],type_ignores=[]),'fit','exec'),ctx)
  good=pd.DataFrame({'M1':[0,1],'R1':[0,1],'age':[np.nan,42]})
  with self.assertRaisesRegex(AssertionError,'Invalid probabilities'):ctx['fit'](good,good)
  with self.assertRaisesRegex(AssertionError,'both classes'):ctx['fit'](good.assign(M1=0),good)
 def test_fake_fit_failure_propagates(self):
  node=next(n for n in MAIN.body if isinstance(n,ast.FunctionDef) and n.name=='fit')
  def gate(ok,msg):
   if not ok:raise AssertionError(msg)
  def fail(*args):raise ValueError('synthetic model failure')
  ctx={'gate':gate,'warnings':warnings,'ConvergenceWarning':ConvergenceWarning,'pairedfit':fail,'Xframe':lambda d:d,'np':np}
  exec(compile(ast.Module(body=[node],type_ignores=[]),'fit','exec'),ctx)
  d=pd.DataFrame({'M1':[0,1],'R1':[0,1],'age':[np.nan,40]})
  with self.assertRaisesRegex(ValueError,'synthetic model failure'):ctx['fit'](d,d)
 def test_seed_and_pair_structure_retained(self):
  self.assertIn('SeedSequence(2026111901).spawn(200)',SRC.read_text())
  self.assertIn('selection[0::2,t]&selection[1::2,t]',SRC.read_text())
  self.assertIn('selection[b,0]&selection[b,1]',SRC.read_text())
 def test_multiset_and_heldout_gate(self):
  source=SRC.read_text().splitlines(); first=next(i for i,s in enumerate(source) if 'tr,te,groups,members=parts[r,fold];' in s)
  code='\n'.join(s.strip() for s in source[first:first+3]);members={'a':np.array([0,1]),'b':np.array([2]),'c':np.array([3,4])}
  class Fixed:
   def integers(self,*args,**kwargs):return np.array([0,0,2])
  def gate(ok,msg):
   if not ok:raise AssertionError(msg)
  d={'np':np,'parts':{(0,0):(np.arange(5),np.array([5]),['a','b','c'],members)},'r':0,'fold':0,'rng':Fixed(),'gate':gate,'communities':np.array(['a','a','b','c','c','z'])}
  exec(code,d);self.assertEqual(d['ix'].tolist(),[0,1,0,1,3,4])
  d['communities'][-1]='a'
  with self.assertRaises(AssertionError):exec(code,d)
if __name__=='__main__':unittest.main(verbosity=2)
