"""Real extracted definitions, synthetic records and inert mock estimators only."""
import ast
from pathlib import Path
import tempfile
import unittest
import warnings
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/'code/stab01/stab01_execution.py'
SOURCE=ROOT/'code/analysis/03_aim3_prediction.py'

class MockComponent:
 def __init__(self,*args,**kwargs):self.n_iter_=np.array([1]);self.kwargs=kwargs
 def transform(self,x):return np.zeros((len(x),1))
class MockPipeline:
 def __init__(self,steps):self.named_steps=dict(steps)
 def fit(self,x,y):return self
 def predict_proba(self,x):return np.tile([0.75,0.25],(len(x),1))

def gate(ok,msg):
 if not ok:raise AssertionError(msg)

def build_probe(source_path, export_names=('Xframe','template','pairedfit','highmask','fit')):
 tree=ast.parse(RUNNER.read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
 start=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='source' for x in n.targets))
 end=next(i for i,n in enumerate(main.body) if isinstance(n,ast.FunctionDef) and n.name=='fit')
 body=main.body[start:end+1]
 body.append(ast.Return(value=ast.Tuple(elts=[ast.Name(id=x,ctx=ast.Load()) for x in export_names],ctx=ast.Load())))
 args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=n) for n in ('inputs','ast','np','Pipeline','ColumnTransformer','SimpleImputer','StandardScaler','OneHotEncoder','LogisticRegression','gate','warnings','ConvergenceWarning')],kwonlyargs=[],kw_defaults=[],defaults=[])
 probe=ast.FunctionDef(name='probe',args=args,body=body,decorator_list=[])
 module=ast.fix_missing_locations(ast.Module(body=[probe],type_ignores=[]));ns={}
 exec(compile(module,'candidate_probe','exec'),ns)
 return ns['probe']({'model_code':(source_path,'unused')},ast,np,MockPipeline,MockComponent,MockComponent,MockComponent,MockComponent,MockComponent,gate,warnings,ConvergenceWarning)

class RuntimeNamespaceTests(unittest.TestCase):
 def test_four_real_functions_and_fit_invocation(self):
  xframe,template,pairedfit,highmask,fit=build_probe(SOURCE)
  for fn in (xframe,template,pairedfit,highmask,fit):self.assertTrue(callable(fn))
  shared=xframe.__globals__
  for fn in (template,pairedfit,highmask):self.assertIs(fn.__globals__,shared)
  for name in ('np','Pipeline','ColumnTransformer','SimpleImputer','StandardScaler','OneHotEncoder','LogisticRegression','blocks'):
   self.assertIn(name,shared)
  frame=pd.DataFrame({'age':[50.,np.nan],'sbp':[130.,140.],'dbp':[80.,90.], 'education':['LOW','HIGH'],'access':['CONTACT','NO_CONTACT'],'female':[0,1],'M1':[0,1],'R1':[1,0],'id':['2','1']})
  result=fit(frame,frame)
  self.assertEqual(set(result),{'M','R'});np.testing.assert_array_equal(result['M'],[.25,.25]);np.testing.assert_array_equal(result['R'],[.25,.25])
  self.assertEqual(int(highmask(np.array([.5,.5]),frame,.5).sum()),1)
  self.assertEqual(np.flatnonzero(highmask(np.array([.5,.5]),frame,.5)).tolist(),[1])
 def test_fit_resolves_dynamically_loaded_pairedfit(self):
  fit,=build_probe(SOURCE,('fit',))
  frame=pd.DataFrame({'age':[50.,np.nan],'sbp':[130.,140.],'dbp':[80.,90.], 'education':['LOW','HIGH'],'access':['CONTACT','NO_CONTACT'],'female':[0,1],'M1':[0,1],'R1':[1,0]})
  result=fit(frame,frame)
  self.assertEqual(set(result),{'M','R'})
 def test_missing_definition_fails(self):
  tree=ast.parse(SOURCE.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'Xframe','template','pairedfit'}]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'missing.py';p.write_text(ast.unparse(ast.Module(body=nodes,type_ignores=[])))
   with self.assertRaisesRegex(AssertionError,'Missing original function definition'):build_probe(p)
 def test_invalid_source_fails(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'invalid.py';p.write_text('def broken(:\n')
   with self.assertRaises(SyntaxError):build_probe(p)
 def test_duplicate_definition_fails(self):
  tree=ast.parse(SOURCE.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'Xframe','template','pairedfit','highmask'}]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'duplicate.py';p.write_text(ast.unparse(ast.Module(body=nodes+[nodes[0]],type_ignores=[])))
   with self.assertRaisesRegex(AssertionError,'Missing original function definition'):build_probe(p)
if __name__=='__main__':unittest.main(verbosity=2)
