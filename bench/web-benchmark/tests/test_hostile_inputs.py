import json
import os
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path


BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

from model import enforce_size_limits, resolve_contained
from run import RedactedJournal, load_samples
from adapters import SubprocessExecutor
import sandbox_exec
from sandbox_exec import CODEC_ENV, MANDATORY_NETWORK_SYSCALLS


class FakeCFunction:
    def __init__(self, implementation):
        self.implementation = implementation

    def __call__(self, *args):
        return self.implementation(*args)


class FakeSeccompLibrary:
    def __init__(self, unresolved: bytes):
        self.released = False
        self.seccomp_init = FakeCFunction(lambda _action: 1)
        self.seccomp_rule_add = FakeCFunction(lambda *_args: 0)
        self.seccomp_syscall_resolve_name = FakeCFunction(
            lambda name: -1 if name == unresolved else 1
        )
        self.seccomp_load = FakeCFunction(lambda _context: 0)
        self.seccomp_release = FakeCFunction(self._release)

    def _release(self, _context):
        self.released = True


class HostileInputTests(unittest.TestCase):
    def test_codec_environment_is_minimal_and_secret_free(self):
        self.assertEqual(
            CODEC_ENV,
            {"LC_ALL": "C", "LANG": "C", "PATH": "/usr/bin:/bin"},
        )

    def test_systemd_timeout_kills_the_entire_codec_process_tree(self):
        try:
            SubprocessExecutor.verify_network_sandbox()
        except (OSError, PermissionError):
            self.skipTest("user systemd PrivateNetwork sandbox is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child_pid_path = root / "child.pid"
            output = root / "output.bin"
            code = (
                "import pathlib,subprocess,sys,time;"
                "p=subprocess.Popen(('/usr/bin/sleep','60'));"
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid),encoding='ascii');"
                "time.sleep(60)"
            )
            executor = SubprocessExecutor(timeout_seconds=0.5, max_output_bytes=4096)
            with self.assertRaises(TimeoutError):
                executor._run(
                    (str(Path(sys.executable).resolve()), "-c", code, str(child_pid_path)),
                    output,
                )
            self.assertTrue(child_pid_path.is_file())
            child_pid = int(child_pid_path.read_text(encoding="ascii"))
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                os.kill(child_pid, signal.SIGKILL)
                self.fail("systemd timeout left a codec child process alive")

    def test_systemd_private_network_blocks_codec_egress(self):
        try:
            SubprocessExecutor.verify_network_sandbox()
        except (OSError, PermissionError):
            self.skipTest("user systemd PrivateNetwork sandbox is unavailable")
        code = (
            "import errno,socket,sys\n"
            "try:\n"
            "    socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n"
            "except OSError as exc:\n"
            "    sys.exit(0 if exc.errno == errno.EPERM else 8)\n"
            "sys.exit(7)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.bin"
            measurement = SubprocessExecutor(
                timeout_seconds=2,
                max_output_bytes=4096,
            )._run(
                (str(Path(sys.executable).resolve()), "-c", code),
                output,
            )
            self.assertEqual(output.read_bytes(), b"")
            self.assertEqual(
                measurement.output_sha256,
                "e3b0c44298fc1c149afbf4c8996fb924"
                "27ae41e4649b934ca495991b7852b855",
            )

    def test_seccomp_fails_closed_when_any_mandatory_syscall_is_unresolved(self):
        for syscall in MANDATORY_NETWORK_SYSCALLS:
            with self.subTest(syscall=syscall):
                library = FakeSeccompLibrary(unresolved=syscall)
                with mock.patch.object(
                    sandbox_exec.ctypes,
                    "CDLL",
                    return_value=library,
                ):
                    with self.assertRaisesRegex(
                        OSError,
                        f"resolve mandatory network syscall {syscall.decode('ascii')}",
                    ):
                        sandbox_exec._install_network_seccomp()
                self.assertTrue(library.released)

    def test_paths_must_remain_inside_the_corpus_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inside = root / "payloads" / "ok.bin"
            inside.parent.mkdir()
            inside.write_bytes(b"ok")
            self.assertEqual(resolve_contained(root, "payloads/ok.bin"), inside.resolve())

            for hostile in ("/etc/passwd", "../escape", "payloads/../../escape"):
                with self.subTest(hostile=hostile):
                    with self.assertRaisesRegex(ValueError, "contained"):
                        resolve_contained(root, hostile)

    def test_symlink_escape_is_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            outside = Path(directory) / "outside.bin"
            root.mkdir()
            outside.write_bytes(b"secret")
            (root / "link.bin").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "contained"):
                resolve_contained(root, "link.bin")

    def test_input_output_and_expansion_limits_are_enforced(self):
        enforce_size_limits(100, 200, max_input_bytes=100, max_output_bytes=200, max_expansion_ratio=2)
        with self.assertRaisesRegex(ValueError, "input"):
            enforce_size_limits(101, 100, max_input_bytes=100, max_output_bytes=200, max_expansion_ratio=2)
        with self.assertRaisesRegex(ValueError, "output"):
            enforce_size_limits(100, 201, max_input_bytes=100, max_output_bytes=200, max_expansion_ratio=3)
        with self.assertRaisesRegex(ValueError, "expansion"):
            enforce_size_limits(100, 201, max_input_bytes=100, max_output_bytes=1000, max_expansion_ratio=2)

    def test_journal_keeps_only_allowlisted_context(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = RedactedJournal(Path(directory) / "voids.jsonl")
            journal.write(
                "crash",
                {
                    "sample_id": "safe-id",
                    "codec_key": "gzip-9",
                    "trial_no": 4,
                    "path": "/private/corpus/input",
                    "stderr": "token=secret",
                },
            )
            record = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertEqual(
                record,
                {
                    "codec_key": "gzip-9",
                    "reason": "crash",
                    "sample_id": "safe-id",
                    "trial_no": 4,
                },
            )

    def test_manifest_rejects_duplicate_ids_and_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload.bin"
            payload.write_bytes(b"x")
            sample = {
                "sample_id": "duplicate",
                "path": "payload.bin",
                "sha256": "a" * 64,
                "byte_count": 1,
                "media_type": "application/octet-stream",
                "size_class": "small",
                "media_family": "binary",
                "source_ref": "project-authored:fixture",
                "license_id": "MIT",
                "redistributable": True,
            }
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"schema_version": 1, "samples": [sample, sample]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_samples(manifest)


if __name__ == "__main__":
    unittest.main()
