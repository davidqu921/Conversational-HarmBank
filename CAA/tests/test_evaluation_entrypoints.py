"""Regression checks for evaluator routing and condition-specific output isolation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import CAA.tests.test_isolated_repeated_attack  # installs optional runtime stubs
from CAA.scripts import code_caa_severity_with_hf as ordinary
from CAA.scripts import evaluate_isolated_repeated_attack as isolated

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / 'CAA/scripts/batch/run_severity.sh'


class EvaluationEntrypointTests(unittest.TestCase):
    def test_both_entries_select_evaluator_with_and_without_compatibility_flag(self):
        class ReachedLegacyConfig(Exception):
            pass

        for module in (ordinary, isolated):
            for flags in ([], ['--legacy-rubric']):
                with self.subTest(module=module.__name__, flags=flags):
                    with patch.object(sys, 'argv', ['evaluate', '--config', 'test.yaml', *flags]):
                        with patch.object(module, 'load_config', side_effect=ReachedLegacyConfig):
                            with self.assertRaises(ReachedLegacyConfig):
                                module.main()


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = self.root / 'calls.jsonl'
        fake = self.root / 'fake_python'
        fake.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
if sys.argv[1] == '-c':
    print('/tmp/experiment with spaces')
else:
    with Path(os.environ['TEST_CALL_LOG']).open('a') as f:
        f.write(json.dumps({'argv':sys.argv[1:], 'cwd':os.getcwd()})+'\\n')
''')
        fake.chmod(0o755)
        self.env = dict(os.environ, PYTHON_BIN=str(fake), TEST_CALL_LOG=str(self.calls))

    def launch(self, *args):
        return subprocess.run(['bash', str(LAUNCHER), 'config.yaml', *args],
                              cwd=self.root, env=self.env, capture_output=True, text=True)

    def records(self):
        return [json.loads(row) for row in self.calls.read_text().splitlines()]

    def test_all_routes_have_separate_inputs_and_outputs_from_any_cwd(self):
        result = self.launch('all', '--dry-run', '--limit', '1')
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.records()
        self.assertEqual(len(rows), 4)
        eval_dirs = ['evaluation',
                     'context_independent_trajectory_seeded_repeated_weak_attack_evaluation',
                     'weak_attack_evaluation']
        input_dirs = ['', 'context_independent_trajectory_seeded_repeated_weak_attack_convos/',
                      'weak_attack_convos/']
        for row, folder, input_folder in zip(rows[:3], eval_dirs, input_dirs):
            args = row['argv']
            self.assertEqual(row['cwd'], str(REPO))
            self.assertIn('CAA.scripts.code_caa_severity_with_hf', args)
            self.assertEqual(args[args.index('--out-dir')+1],
                f'/tmp/experiment with spaces/{folder}/dual-layer_human-aligned-v2_llama31_and_mistral')
            self.assertEqual(args[args.index('--transcripts')+1],
                f'/tmp/experiment with spaces/{input_folder}transcripts.jsonl')
        self.assertIn('CAA.scripts.evaluate_isolated_repeated_attack', rows[-1]['argv'])
        self.assertNotIn('--transcripts', rows[-1]['argv'])
        for row in rows:
            for flag in ['--double-layer', '--resume', '--dry-run']:
                self.assertIn(flag, row['argv'])

    def test_all_rejects_shared_output_and_reference(self):
        for flag in ['--out-dir', '--out-dir=shared', '--reference-codings', '--reference-codings=shared']:
            with self.subTest(flag=flag):
                self.assertEqual(self.launch('all', flag).returncode, 2)
        self.assertFalse(self.calls.exists())

    def test_rejects_condition_overrides_and_single_layer(self):
        for flag in ['--transcripts', '--config', '--parent-index', '--no-double-layer']:
            with self.subTest(flag=flag):
                self.assertEqual(self.launch('isolated', flag).returncode, 2)
        self.assertFalse(self.calls.exists())

    def test_unknown_condition_fails_before_model_invocation(self):
        self.assertEqual(self.launch('misspelled').returncode, 2)
        self.assertFalse(self.calls.exists())

    def test_default_condition_and_explicit_existing_output(self):
        result = self.launch('--out-dir', '/tmp/existing legacy run')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.records()[0]['argv']
        self.assertIn('/tmp/experiment with spaces/context_independent_trajectory_seeded_repeated_weak_attack_convos/transcripts.jsonl', args)
        # argparse keeps the final occurrence of --out-dir.
        self.assertEqual(args[-2:], ['--out-dir', '/tmp/existing legacy run'])


if __name__ == '__main__':
    unittest.main()
