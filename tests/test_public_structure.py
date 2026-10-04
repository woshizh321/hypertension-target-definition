"""Dependency-free structural checks. Never imports scientific scripts."""
from pathlib import Path
import ast,json,unittest
ROOT=Path(__file__).resolve().parents[1]
class PublicStructure(unittest.TestCase):
 def test_python_syntax(self):
  for p in (ROOT/'code').rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
 def test_code_only_scope(self):
  for p in ROOT.rglob('*'):
   if p.is_file() and '.git' not in p.parts:
    self.assertNotIn(p.suffix.lower(),['.csv','.parquet','.dta','.xpt','.xlsx','.joblib','.pkl','.zip','.duckdb','.pdf','.png'])
 def test_primary_contract(self):
  c=json.loads((ROOT/'documentation/primary_label_contract.json').read_text())
  self.assertEqual(len(c['blocks']),7)
  self.assertEqual([(p['dataset'],p['baseline'],p['followup']) for p in c['primary_pairs']],[('CHARLS','2013','2015'),('ELSA','4','6'),('HRS','2014','2018')])
  keys=json.loads((ROOT/'documentation/source_paths.example.json').read_text())
  for b in c['blocks']:
   for k in ['health_path','physical_path','weight_path']:
    self.assertIn(b[k],keys)
 def test_no_historical_variants(self):
  self.assertFalse(any('PRE_REPAIR' in p.name for p in ROOT.rglob('*')))
if __name__=='__main__':unittest.main()
