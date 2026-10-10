"""Synthetic CORR01 regression checks; never import or run a data pipeline."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'eb3ac6aaf30797865bd3a31a851a0f4d40c91bcf'
ADAPTER = 'code/label_derivation/02_construct_primary_labels.py'
CONTRACT = 'documentation/primary_label_contract.json'
spec = importlib.util.spec_from_file_location(
    'hrs_recognition', ROOT / 'code/label_derivation/hrs_recognition.py'
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
contract = json.loads((ROOT / CONTRACT).read_text())
baseline_contract = json.loads(subprocess.check_output(
    ['git', 'show', BASELINE + ':' + CONTRACT], cwd=ROOT, text=True
))
baseline_source = subprocess.check_output(
    ['git', 'show', BASELINE + ':' + ADAPTER], cwd=ROOT, text=True
)


def isolated_functions(source, mapping=helper.map_hrs_recognition):
    """Compile only real adapter function definitions, excluding top-level I/O.

    This is an AST slice of the production implementation, not a copy of its
    rules. No scientific script import or licensed source read is performed.
    """
    wanted = {'number', 'rt_reason', 'construct_rt', 'bp_construct'}
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in nodes} == wanted
    context = {
        'pd': pd, 'np': np, 'map_hrs_recognition': mapping, 'QC': [],
        'MD': json.loads((ROOT / 'documentation/bp_missing_code_keys.json').read_text()),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), ADAPTER, 'exec'), context)
    return context


def block(dataset, wave):
    return next(b for b in contract['blocks']
                if b['dataset'] == dataset and b['wave'] == wave)


class HRSRecognition(unittest.TestCase):
    def test_2014_oc005_mapping_and_unknowns(self):
        got = helper.map_hrs_recognition(pd.Series([1, 3, 4, 5, 6, 8, 9, None]),
                                         '2014', ['OC005'])
        pd.testing.assert_series_equal(got, pd.Series([1., 1., 0., 0., np.nan,
                                                      np.nan, np.nan, np.nan]))

    def test_2018_qc005_mapping_and_unknowns(self):
        values = pd.Series([1, 6, 4, 5, 3, 8, 9, None, np.nan, pd.NA, '', '.d', 2, 7, '6'])
        got = helper.map_hrs_recognition(values, '2018', ['QC005'])
        pd.testing.assert_series_equal(got, pd.Series([1., 1., 0., 0.] +
                                                      [np.nan] * 10 + [1.]))

    def test_wave_and_source_field_guard(self):
        # Preserve the exact audited conditional guard, not a new fallback rule.
        values = pd.Series([3, 6])
        for wave, fields in [('2014', ['OC005']), ('2018', ['OC005']),
                             ('2014', ['QC005'])]:
            with self.subTest(wave=wave, fields=fields):
                pd.testing.assert_series_equal(
                    helper.map_hrs_recognition(values, wave, fields),
                    pd.Series([1., np.nan]))

    def test_actual_adapter_no_auxiliary_confirmation_and_status_schema(self):
        b = block('HRS', '2018')
        # All fixtures are fabricated category values; no participant identifiers.
        d = pd.DataFrame({'QC005': [6, 6, 6, 3, 4, 5, 8, 9, None],
                          'QC006': [np.nan, 5, 1, 1, 5, 8, 9, None, 1]})
        api = isolated_functions((ROOT / ADAPTER).read_text())
        out = api['construct_rt'](d.copy(), b)
        self.assertEqual(out.R.iloc[:3].tolist(), [1., 1., 1.])
        self.assertTrue(pd.isna(out.R.iloc[3]))
        self.assertEqual(out.R.iloc[4:6].tolist(), [0., 0.])
        self.assertEqual(out.R_status.iloc[0], 'EXPLICIT_AFFIRMATIVE_SOURCE_OR_CONFIRMED_DOCTOR_HISTORY')
        self.assertEqual(out.R_status.iloc[3], 'UNRESOLVED_SOURCE_RESPONSE_OR_ROUTING')
        self.assertEqual(out.R_status.iloc[6], 'DONT_KNOW')
        self.assertEqual(out.R_status.iloc[7], 'REFUSED')
        self.assertEqual(out.R_status.iloc[8], 'SOURCE_BLANK_OR_TAGGED_MISSING_ROUTING_UNKNOWN')
        old = isolated_functions(baseline_source)['construct_rt'](d.copy(), b)
        self.assertEqual(list(out.columns), list(old.columns))
        for col in ['T', 'T_status', 'R_dispute_retraction',
                    'T_response_contradiction', 'source_QC005', 'source_QC006']:
            pd.testing.assert_series_equal(out[col], old[col])
        # Auxiliary preload/confirmation values cannot control R.
        for preload in [1, 5, np.nan]:
            augmented = d.assign(QZ101=preload)
            pd.testing.assert_series_equal(
                api['construct_rt'](augmented, b).R, out.R)

    def test_actual_bp_and_t_unchanged_for_identical_synthetic_rows(self):
        for wave in ['2014', '2018']:
            with self.subTest(wave=wave):
                b = block('HRS', wave)
                d = pd.DataFrame({b['R_fields'][0]: [1, 3, 4, 5, 6, 8, 9, None],
                                  b['T_fields'][0]: [1, 5, 8, 9, None, 1, 5, 6]})
                for field in b['SBP']: d[field] = [139, 140, 160, 120, 130, 0, 170, np.nan]
                for field in b['DBP']: d[field] = [89, 80, 95, 90, 85, 80, 100, np.nan]
                old_api = isolated_functions(baseline_source)
                new_api = isolated_functions((ROOT / ADAPTER).read_text())
                old = old_api['bp_construct'](old_api['construct_rt'](d.copy(), b), b)
                new = new_api['bp_construct'](new_api['construct_rt'](d.copy(), b), b)
                permitted = {'R', 'R_status'} if wave == '2018' else set()
                self.assertEqual(list(old.columns), list(new.columns))
                for col in old.columns:
                    if col not in permitted:
                        pd.testing.assert_series_equal(old[col], new[col])
                self.assertEqual(new.M.iloc[:5].tolist(), [0., 1., 1., 1., 0.])

    def test_non_hrs_branches_do_not_invoke_mapping(self):
        forbidden = Mock(side_effect=AssertionError('Non-HRS invoked HRS mapping'))
        api = isolated_functions((ROOT / ADAPTER).read_text(), mapping=forbidden)
        old_api = isolated_functions(baseline_source)
        for b in contract['blocks']:
            if b['dataset'] == 'HRS': continue
            with self.subTest(dataset=b['dataset'], wave=b['wave']):
                fields = set(b['R_fields'] + b['T_fields'])
                d = pd.DataFrame({f: [1, 2, np.nan] for f in fields})
                pd.testing.assert_frame_equal(
                    api['construct_rt'](d.copy(), b),
                    old_api['construct_rt'](d.copy(), b))
        forbidden.assert_not_called()

    def test_contract_scope_and_executable_agreement(self):
        expected_rule = 'HRS_2018_QC005_1_6_YES_4_5_NO_3_UNSUPPORTED_OTHER_UNKNOWN_HISTORICAL_RECOGNITION'
        for old, new in zip(baseline_contract['blocks'], contract['blocks']):
            if new['dataset'] == 'HRS' and new['wave'] == '2018':
                self.assertEqual(new['R_rule'], expected_rule)
                restored = dict(new, R_rule=old['R_rule'])
                self.assertEqual(restored, old)
                result = helper.map_hrs_recognition(pd.Series([1, 6, 4, 5, 3]),
                                                   new['wave'], new['R_fields'])
                pd.testing.assert_series_equal(result, pd.Series([1., 1., 0., 0., np.nan]))
            else:
                self.assertEqual(new, old)
        self.assertEqual(contract['primary_pairs'], baseline_contract['primary_pairs'])
        self.assertEqual(contract['policies'], baseline_contract['policies'])

    def test_only_authorized_adapter_function_change(self):
        original = ast.parse(baseline_source)
        current = ast.parse((ROOT / ADAPTER).read_text())
        old_functions = {n.name: n for n in original.body if isinstance(n, ast.FunctionDef)}
        new_functions = {n.name: n for n in current.body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(set(old_functions), set(new_functions))
        for name in old_functions:
            if name != 'construct_rt':
                self.assertEqual(ast.dump(old_functions[name]), ast.dump(new_functions[name]), name)
        # Restore just the HRS R assignment to prove all other branch code agrees.
        old_fn, new_fn = old_functions['construct_rt'], new_functions['construct_rt']
        def hrs_branch(fn):
            return next(n for n in ast.walk(fn) if isinstance(n, ast.If)
                        and ast.dump(n.test) == ast.dump(ast.parse("ds == 'HRS'", mode='eval').body))
        old_hrs, new_hrs = hrs_branch(old_fn), hrs_branch(new_fn)
        self.assertEqual(len(old_hrs.body), len(new_hrs.body))
        self.assertEqual(ast.unparse(new_hrs.body[0]),
                         "R = map_hrs_recognition(n[b['R_fields'][0]], b['wave'], b['R_fields'])")
        new_hrs.body[0] = old_hrs.body[0]
        self.assertEqual(ast.dump(old_fn), ast.dump(new_fn))
        # Restore authorized import too; top-level source-processing stays exact.
        current.body = [n for n in current.body
                        if not (isinstance(n, ast.ImportFrom) and n.module == 'hrs_recognition')]
        self.assertEqual(ast.dump(current), ast.dump(original))

    def test_helper_has_no_file_network_or_pipeline_dependencies(self):
        source = (ROOT / 'code/label_derivation/hrs_recognition.py').read_text()
        tree = ast.parse(source)
        self.assertTrue(all(isinstance(n, (ast.Expr, ast.Import, ast.FunctionDef))
                            for n in tree.body))
        imports = [n.names[0].name for n in tree.body if isinstance(n, ast.Import)]
        self.assertEqual(imports, ['pandas'])
        with patch('builtins.open', side_effect=AssertionError('Unexpected source read')):
            result = helper.map_hrs_recognition(pd.Series([6]), '2018', ['QC005'])
        self.assertEqual(result.iloc[0], 1.)


if __name__ == '__main__':
    unittest.main()
