"""Synthetic private-authority tests. No study data, model fitting or bootstrap."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('stab01_identity_guard',ROOT/'code/stab01/identity_guard.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode()
class PrivateIdentityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.records={};hashes={}
  for name in sorted(guard.REQUIRED):
   f=self.root/name;data=('synthetic-'+name).encode();f.write_bytes(data)
   hashes[name]=sha(data);self.records[name]={'path':str(f),'sha256':hashes[name]}
  self.ref={'schema':guard.REFERENCE_SCHEMA,'source_sha256':sha(b'synthetic-code'),'input_sha256':hashes}
  self.path=self.root/'reference.json';self.raw=canonical(self.ref);self.path.write_bytes(self.raw)
  self.auth=self.root/'authority.json';self.auth.write_text(json.dumps({'schema':guard.AUTHORITY_SCHEMA,'reference_sha256':sha(self.raw)}));self.auth.chmod(0o600)
  self.env=patch.dict(os.environ,{'STAB01_PRIVATE_AUTHORITY':str(self.auth)});self.env.start();self.addCleanup(self.env.stop)
 def verify(self):return guard.verify_frozen_inputs(self.path,self.records)
 def test_valid_private_authority_and_inputs(self):self.assertEqual(set(self.verify()),guard.REQUIRED)
 def test_missing_private_authority(self):
  self.auth.unlink()
  with self.assertRaises(guard.IdentityError):self.verify()
 def test_missing_authority_environment(self):
  with patch.dict(os.environ,{'STAB01_PRIVATE_AUTHORITY':''}):
   with self.assertRaises(guard.IdentityError):self.verify()
 def test_unsafe_authority_permissions(self):
  self.auth.chmod(0o644)
  with self.assertRaises(guard.IdentityError):self.verify()
 def test_altered_reference_and_matching_inputs(self):
  data=b'changed synthetic data';(self.root/'analytic').write_bytes(data);h=sha(data)
  self.ref['input_sha256']['analytic']=h;self.records['analytic']['sha256']=h;self.path.write_bytes(canonical(self.ref))
  with self.assertRaises(guard.IdentityError):self.verify()
 def test_altered_input(self):
  (self.root/'analytic').write_text('changed')
  with self.assertRaises(guard.IdentityError):self.verify()
 def test_invalid_authority_schema(self):
  self.auth.write_text(json.dumps({'schema':'invalid','reference_sha256':sha(self.raw)}))
  with self.assertRaises(guard.IdentityError):self.verify()
 def test_runner_missing_authority_creates_no_output(self):
  output=self.root/'uncreated';manifest=self.root/'manifest.json'
  manifest.write_text(json.dumps({'inputs':self.records,'output_dir':str(output)}))
  env=dict(os.environ,STAB01_RUN_AUTHORIZED='YES',STAB01_PRIVATE_INPUT_MANIFEST=str(manifest),STAB01_TRUSTED_REFERENCE=str(self.path))
  env.pop('STAB01_PRIVATE_AUTHORITY',None)
  result=subprocess.run([sys.executable,str(ROOT/'code/stab01/stab01_execution.py')],env=env,capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn('Trusted private authority is required',result.stderr)
  self.assertFalse(output.exists())
 def test_incomplete_inputs(self):
  del self.records['folds']
  with self.assertRaises(guard.IdentityError):self.verify()
if __name__=='__main__':unittest.main(verbosity=2)
