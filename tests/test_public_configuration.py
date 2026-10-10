"""Public configuration schema checks; no private configuration is loaded."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicConfiguration(unittest.TestCase):
    def test_primary_contract_schema(self):
        c = json.loads((ROOT / 'documentation/primary_label_contract.json').read_text())
        self.assertEqual(set(c), {'blocks', 'primary_pairs', 'policies'})
        self.assertEqual(len(c['blocks']), 7)
        required = {'dataset', 'wave', 'key', 'health_path', 'physical_path',
                    'weight_path', 'R_fields', 'T_fields', 'SBP', 'DBP',
                    'proxy_fields', 'BP_extra_fields', 'weight', 'strata', 'PSU',
                    'weight_status', 'M_rule', 'R_rule', 'T_rule', 'population',
                    'proxy_rule', 'BP_missing', 'DBP_zero_valid'}
        self.assertEqual(len({(b['dataset'], b['wave']) for b in c['blocks']}), 7)
        paths = json.loads((ROOT / 'documentation/source_paths.example.json').read_text())
        for b in c['blocks']:
            self.assertTrue(required <= set(b))
            for field in ['R_fields', 'T_fields', 'SBP', 'DBP', 'BP_missing']:
                self.assertIsInstance(b[field], list)
            self.assertEqual(len(b['SBP']), len(b['DBP']))
            self.assertIsInstance(b['DBP_zero_valid'], bool)
            for field in ['health_path', 'physical_path', 'weight_path', 'status_path']:
                if field in b: self.assertIn(b[field], paths)

    def test_public_json_parse_and_source_template(self):
        for path in (ROOT / 'documentation').glob('*.json'):
            json.loads(path.read_text())
        paths = json.loads((ROOT / 'documentation/source_paths.example.json').read_text())
        for value in paths.values():
            self.assertIsInstance(value, str)
            self.assertFalse(Path(value).is_absolute())
            self.assertNotIn('..', Path(value).parts)


if __name__ == '__main__':
    unittest.main()
