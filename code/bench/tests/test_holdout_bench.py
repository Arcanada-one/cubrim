"""Behavioral tests with deterministic stand-in CLIs; no compression benchmarks."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "holdout", Path(__file__).resolve().parents[1] / "run_holdout_bench.py"
)
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)

FAKE_CLI = r'''
import json, pathlib, sys, time
root = pathlib.Path(__file__).parent
name = pathlib.Path(__file__).name
if '--version' in sys.argv:
    print(name + ' fixture 1')
    sys.exit(0)
with (root / 'calls.jsonl').open('a') as log:
    log.write(json.dumps([name, *sys.argv[1:]]) + '\n')
mode_path = root / (name + '.mode')
mode = mode_path.read_text() if mode_path.exists() else ''
decode = sys.argv[1] == 'decompress' if name == 'cubrim' else '-d' in sys.argv
src = pathlib.Path(sys.argv[2] if name == 'cubrim' else sys.argv[-1])
if mode == 'slow':
    time.sleep(5)
if mode == 'fail' or (mode == 'decode-fail' and decode):
    sys.stdout.buffer.write(b'partial')
    sys.stderr.write('fixture command failed')
    sys.exit(17)
if mode == 'no-output' or (mode == 'no-decoded' and decode):
    sys.exit(0)
data = src.read_bytes()
header = b'HOLDOUT-FIXTURE:'
if decode:
    assert data.startswith(header)
    output = data[len(header):]
    if mode == 'corrupt':
        output = bytes([output[0] ^ 1]) + output[1:]
else:
    output = header + data
if name == 'cubrim':
    pathlib.Path(sys.argv[3]).write_bytes(output)
else:
    sys.stdout.buffer.write(output)
if mode == 'mutate-input' and not decode:
    src.write_bytes(b'Z' * len(data))
'''


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = self.root / 'holdout'
        self.corpus.mkdir()
        self.output = self.root / 'reports'
        self.tools_dir = self.root / 'tools'
        self.tools_dir.mkdir()
        self.tools = {}
        for name in ('cubrim', 'gzip', 'zstd'):
            path = self.tools_dir / name
            path.write_text('#!' + sys.executable + ' -S\n' + textwrap.dedent(FAKE_CLI))
            path.chmod(0o755)
            self.tools[name] = str(path)
        self.data = (b'held-out input\x00\xff\n' * 40)
        self.entries = []
        self.add_input('sample file.bin', self.data)
        self.manifest = self.corpus / 'manifest.json'
        self.write_manifest()
        patches = {
            'HOLDOUT_DIR': self.corpus, 'MANIFEST': self.manifest,
            'RESEARCH_DIR': self.output, 'CUBRIM_BIN': Path(self.tools['cubrim']),
        }
        for key, value in patches.items():
            patch = mock.patch.object(bench, key, value)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(bench.shutil, 'which', side_effect=lambda name: self.tools.get(name))
        patch.start()
        self.addCleanup(patch.stop)
        self.env_patch = mock.patch.object(bench, 'gather_env', side_effect=self.fixture_env)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def add_input(self, name, data):
        (self.corpus / name).write_bytes(data)
        self.entries.append({'name': name, 'category': 'test-fixture',
                             'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.entries))

    def fixture_env(self, tools, manifest_sha):
        return {'code_sha': 'a' * 40, 'fixture_only': True,
                'manifest_sha256': manifest_sha,
                'binaries': {name: {'path': path, 'sha256': bench.file_sha256(Path(path)),
                                    'size_bytes': Path(path).stat().st_size}
                             for name, path in tools.items()}}

    def mode(self, name, mode):
        (self.tools_dir / (name + '.mode')).write_text(mode)

    def run_main(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = bench.main(['--report-id', 'unit-test', *args])
        self.stderr = stderr.getvalue()
        self.stdout = stdout.getvalue()
        return code

    def assert_aborted(self, message=None, no_commands=False, *args):
        self.assertEqual(self.run_main(*args), 1)
        self.assertFalse((self.output / 'unit-test-bench.json').exists())
        if message:
            self.assertIn(message, self.stderr)
        if no_commands:
            self.assertFalse((self.tools_dir / 'calls.jsonl').exists())

    def test_complete_report_preserves_numeric_fields_and_all_roundtrips(self):
        self.add_input('second.bin', b'x' * 80)
        self.write_manifest()
        self.assertEqual(self.run_main(), 0)
        report = json.loads((self.output / 'unit-test-bench.json').read_text())
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['schema_version'], 2)
        self.assertEqual(report['round_trip_all'], 'PASS')
        self.assertEqual(report['environment']['manifest_sha256'], bench.file_sha256(self.manifest))
        size = len(self.data) + 80
        total = size + 2 * len(b'HOLDOUT-FIXTURE:')
        self.assertEqual(report['totals']['input_bytes'], size)
        for key in ['cubrim_bwt-rans', 'cubrim_bwt-geomix', 'gzip', 'zstd']:
            self.assertEqual(report['totals'][key + '_bytes'], total)
            self.assertEqual(report['aggregate'][key], round(total / size, 6))
            for row in report['results']:
                self.assertGreater(row['timings'][key]['compression_seconds'], 0)
                self.assertGreater(row['timings'][key]['decompression_seconds'], 0)
                self.assertEqual(row['timings'][key]['round_trip'], 'PASS')
        self.assertEqual(len(report['commands']), 16)

    def test_missing_zstd_never_becomes_zero_size(self):
        del self.tools['zstd']
        self.assert_aborted('required comparator not found: zstd', no_commands=True)

    def test_missing_gzip_aborts_before_compression(self):
        del self.tools['gzip']
        self.assert_aborted('required comparator not found: gzip', no_commands=True)

    def test_non_executable_cubrim_aborts(self):
        Path(self.tools['cubrim']).chmod(0o644)
        self.assert_aborted('executable Cubrim', no_commands=True)

    def test_size_mismatch_aborts_before_compression(self):
        self.entries[0]['size_bytes'] += 1
        self.write_manifest()
        self.assert_aborted('size mismatch', no_commands=True)

    def test_equal_length_input_mutation_is_detected(self):
        (self.corpus / self.entries[0]['name']).write_bytes(b'X' * len(self.data))
        self.assert_aborted('sha256 mismatch', no_commands=True)

    def test_late_invalid_entry_rejects_whole_corpus_before_any_codec(self):
        self.add_input('last.bin', b'other')
        self.entries[-1]['sha256'] = '0' * 64
        self.write_manifest()
        self.assert_aborted('sha256 mismatch', no_commands=True)

    def test_missing_hash_rejected(self):
        del self.entries[0]['sha256']
        self.write_manifest()
        self.assert_aborted('sha256 is required', no_commands=True)

    def test_duplicate_file_rejected(self):
        self.entries.append(self.entries[0].copy())
        self.write_manifest()
        self.assert_aborted('duplicate', no_commands=True)

    def test_empty_manifest_rejected(self):
        self.entries = []
        self.write_manifest()
        self.assert_aborted('non-empty list', no_commands=True)

    def test_object_manifest_rejected(self):
        self.manifest.write_text('{}')
        self.assert_aborted('non-empty list', no_commands=True)

    def test_malformed_json_rejected(self):
        self.manifest.write_text('[broken')
        self.assert_aborted('invalid manifest', no_commands=True)

    def test_non_object_entry_rejected(self):
        self.manifest.write_text('[7]')
        self.assert_aborted('must be an object', no_commands=True)

    def test_boolean_size_rejected(self):
        self.entries[0]['size_bytes'] = True
        self.write_manifest()
        self.assert_aborted('positive integer', no_commands=True)

    def test_empty_input_rejected_in_ratio_corpus(self):
        self.add_input('empty.bin', b'')
        self.write_manifest()
        self.assert_aborted('positive integer', no_commands=True)

    def test_traversal_rejected(self):
        self.entries[0]['name'] = '../outside.bin'
        self.write_manifest()
        self.assert_aborted('single file names', no_commands=True)

    def test_symlink_rejected(self):
        src = self.corpus / self.entries[0]['name']
        src.unlink()
        outside = self.root / 'outside.bin'
        outside.write_bytes(self.data)
        src.symlink_to(outside)
        self.assert_aborted('regular file', no_commands=True)

    def test_shell_metacharacters_are_literal_filename(self):
        self.entries = []
        self.add_input('a; echo INJECTED; $(echo bad).bin', self.data)
        self.write_manifest()
        self.assertEqual(self.run_main(), 0)
        self.assertNotIn('INJECTED\n', self.stdout)
        self.assertEqual((self.corpus / self.entries[0]['name']).read_bytes(), self.data)

    def test_gzip_partial_stdout_and_failure_not_counted(self):
        self.mode('gzip', 'fail')
        self.assert_aborted('command failed (17)')

    def test_zstd_partial_stdout_and_failure_not_counted(self):
        self.mode('zstd', 'fail')
        self.assert_aborted('command failed (17)')

    def test_success_without_compressed_output_rejected(self):
        self.mode('gzip', 'no-output')
        self.assert_aborted('no compressed output')

    def test_cubrim_compress_failure_rejected(self):
        self.mode('cubrim', 'fail')
        self.assert_aborted('command failed (17)')

    def test_cubrim_decompress_failure_rejected(self):
        self.mode('cubrim', 'decode-fail')
        self.assert_aborted('command failed (17)')

    def test_missing_decoded_file_is_not_a_pass(self):
        self.mode('cubrim', 'no-decoded')
        self.assert_aborted('round-trip mismatch')

    def test_equal_length_cubrim_corruption_rejected(self):
        self.mode('cubrim', 'corrupt')
        self.assert_aborted('round-trip mismatch')

    def test_gzip_corruption_rejected(self):
        self.mode('gzip', 'corrupt')
        self.assert_aborted('round-trip mismatch')

    def test_zstd_corruption_rejected(self):
        self.mode('zstd', 'corrupt')
        self.assert_aborted('round-trip mismatch')

    def test_mutated_private_input_not_accepted(self):
        self.mode('cubrim', 'mutate-input')
        self.assert_aborted('round-trip mismatch')
        self.assertEqual((self.corpus / self.entries[0]['name']).read_bytes(), self.data)

    def test_existing_report_is_preserved_and_nothing_runs(self):
        self.output.mkdir()
        report = self.output / 'unit-test-bench.json'
        report.write_text('previous report')
        self.assertEqual(self.run_main(), 1)
        self.assertEqual(report.read_text(), 'previous report')
        self.assertFalse((self.tools_dir / 'calls.jsonl').exists())

    def test_report_id_cannot_escape_output_directory(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            bench.main(['--report-id', '../escape'])
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_invalid_time_limits_rejected(self):
        for value in ('nan', 'inf', '0', '-1'):
            with self.subTest(value=value):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    bench.main(['--timeout-seconds', value])

    def test_command_timeout_aborts_without_report(self):
        self.mode('cubrim', 'slow')
        start = time.monotonic()
        self.assertEqual(self.run_main('--timeout-seconds', '0.1'), 1)
        self.assertIn('timed out', self.stderr)
        self.assertLess(time.monotonic() - start, 2)
        self.assertFalse(self.output.exists())

    def test_campaign_deadline_limits_command(self):
        self.mode('cubrim', 'slow')
        start = time.monotonic()
        self.assertEqual(self.run_main('--total-timeout-seconds', '0.1'), 1)
        self.assertLess(time.monotonic() - start, 2)
        self.assertFalse(self.output.exists())

    def test_expired_deadline_does_not_launch(self):
        runner = bench.Runner(10, time.monotonic() - 1)
        with self.assertRaisesRegex(bench.BenchmarkError, 'campaign time limit'):
            runner.run([self.tools['cubrim'], 'compress', 'unused', 'unused'])
        self.assertEqual(runner.commands, [])

    def test_binary_fingerprint_change_rejected(self):
        original = self.fixture_env
        def stale(tools, sha):
            result = original(tools, sha)
            result['binaries']['cubrim']['sha256'] = '0' * 64
            return result
        bench.gather_env.side_effect = stale
        self.assert_aborted('binary changed')

    def test_repository_provenance_is_not_inferred_from_working_directory(self):
        self.env_patch.stop()
        expected_sha = '1' * 40
        def command_result(command, **kwargs):
            self.assertEqual(kwargs['cwd'], bench._PROJECT)
            self.assertNotIn('shell', kwargs)
            output = expected_sha if command[1:3] == ['rev-parse', 'HEAD'] else ''
            return subprocess.CompletedProcess(command, 0, output, '')
        with mock.patch.object(bench.subprocess, 'run', side_effect=command_result), \
                mock.patch.object(bench.platform, 'platform', return_value='fixture OS'):
            result = bench.gather_env(self.tools, bench.file_sha256(self.manifest))
        self.assertEqual(result['code_sha'], expected_sha)
        self.assertEqual(result['binaries']['cubrim']['sha256'], bench.file_sha256(Path(self.tools['cubrim'])))
        self.assertFalse(result['working_tree_dirty'])

    def test_unavailable_git_prevents_attributable_report(self):
        self.env_patch.stop()
        with mock.patch.object(bench.subprocess, 'run', side_effect=FileNotFoundError('git')):
            self.assert_aborted('repository provenance', no_commands=True)


class RunnerTests(unittest.TestCase):
    def test_atomic_report_does_not_replace_concurrent_result(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'result.json'
            report.write_text('previous')
            with self.assertRaises(FileExistsError):
                bench.publish_report(report, '{"new": true}')
            self.assertEqual(report.read_text(), 'previous')
            self.assertEqual(list(Path(directory).glob('.holdout-*')), [])

    def test_failed_publication_leaves_no_partial_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'result.json'
            with mock.patch.object(bench.os, 'link', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    bench.publish_report(report, '{"new": true}')
            self.assertFalse(report.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_byte_comparison_checks_beyond_one_chunk(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / 'a', Path(directory) / 'b'
            data = b'a' * (bench.CHUNK_BYTES + 20)
            a.write_bytes(data)
            b.write_bytes(data[:-1] + b'b')
            self.assertFalse(bench.files_equal(a, b))
            b.write_bytes(data)
            self.assertTrue(bench.files_equal(a, b))

    @unittest.skipUnless(os.name == 'posix', 'process group cleanup is Unix-specific')
    def test_timeout_stops_descendant_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'descendant-survived'
            child = f'import time,pathlib;time.sleep(0.4);pathlib.Path({str(marker)!r}).touch()'
            parent = f'import subprocess,sys,time;subprocess.Popen([sys.executable,"-S","-c",{child!r}]);time.sleep(5)'
            runner = bench.Runner(0.15, time.monotonic() + 2)
            with self.assertRaisesRegex(bench.BenchmarkError, 'timed out'):
                runner.run([sys.executable, '-S', '-c', parent])
            time.sleep(0.5)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
