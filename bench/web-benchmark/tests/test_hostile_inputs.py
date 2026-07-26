import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

from model import enforce_size_limits, resolve_contained
from run import RedactedJournal, load_samples


class HostileInputTests(unittest.TestCase):
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
                    "codec_key": "gzip",
                    "trial_no": 4,
                    "path": "/private/corpus/input",
                    "stderr": "token=secret",
                },
            )
            record = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertEqual(
                record,
                {
                    "codec_key": "gzip",
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
