import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CORPUS_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = CORPUS_ROOT / "manifest.v1.json"
CHECKSUM_PATH = CORPUS_ROOT / "MANIFEST.sha256"
PAYLOADS_ROOT = (CORPUS_ROOT / "payloads").resolve()

EXPECTED_MEDIA_FAMILIES = {
    "html",
    "css",
    "javascript",
    "source-map",
    "json-api",
    "svg",
    "wasm",
    "woff2",
}
SIZE_CLASS_BOUNDS = {
    "small": (1_024, 10_240),
    "medium": (10_241, 262_144),
    "large": (262_145, 2_097_152),
}
REQUIRED_FIELDS = {
    "sample_id",
    "path",
    "media_type",
    "media_family",
    "size_class",
    "byte_count",
    "sha256",
    "source_ref",
    "license_id",
    "redistributable",
}

VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "web_corpus_verify_manifest",
    CORPUS_ROOT / "verify_manifest.py",
)
VERIFIER = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(VERIFIER)


def load_manifest():
    if not MANIFEST_PATH.is_file():
        raise AssertionError(f"missing manifest: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def write_manifest_and_checksum(corpus_root, manifest):
    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    (corpus_root / "manifest.v1.json").write_bytes(canonical)
    digest = hashlib.sha256(canonical).hexdigest()
    (corpus_root / "MANIFEST.sha256").write_text(
        f"{digest}  bench/web-corpus/manifest.v1.json\n",
        encoding="ascii",
    )


def copy_corpus_to_temporary_repository(temporary_directory):
    repository_root = Path(temporary_directory)
    corpus_root = repository_root / "bench" / "web-corpus"
    shutil.copytree(
        CORPUS_ROOT,
        corpus_root,
        ignore=shutil.ignore_patterns("tests", "__pycache__"),
    )
    return repository_root, corpus_root


def run_verifier(repository_root, corpus_root):
    return subprocess.run(
        [sys.executable, str(corpus_root / "verify_manifest.py"), "--check"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )


class WebCorpusManifestTests(unittest.TestCase):
    def test_manifest_covers_required_media_families(self):
        samples = load_manifest()["samples"]
        self.assertEqual(
            EXPECTED_MEDIA_FAMILIES,
            {sample["media_family"] for sample in samples},
        )

    def test_manifest_covers_all_size_classes_and_respects_bounds(self):
        samples = load_manifest()["samples"]
        self.assertEqual(
            set(SIZE_CLASS_BOUNDS),
            {sample["size_class"] for sample in samples},
        )
        for sample in samples:
            lower, upper = SIZE_CLASS_BOUNDS[sample["size_class"]]
            self.assertGreaterEqual(sample["byte_count"], lower)
            self.assertLessEqual(sample["byte_count"], upper)

    def test_each_entry_has_required_metadata_and_redistribution_rights(self):
        samples = load_manifest()["samples"]
        self.assertTrue(samples)
        for sample in samples:
            self.assertTrue(REQUIRED_FIELDS.issubset(sample))
            self.assertIs(sample["redistributable"], True)
            for field in ("sample_id", "path", "media_type", "source_ref", "license_id"):
                self.assertIsInstance(sample[field], str)
                self.assertTrue(sample[field])

    def test_sample_ids_and_paths_are_unique(self):
        samples = load_manifest()["samples"]
        sample_ids = [sample["sample_id"] for sample in samples]
        paths = [sample["path"] for sample in samples]
        self.assertEqual(len(sample_ids), len(set(sample_ids)))
        self.assertEqual(len(paths), len(set(paths)))

    def test_payloads_are_contained_and_match_manifest_digests(self):
        for sample in load_manifest()["samples"]:
            relative_path = Path(sample["path"])
            self.assertFalse(relative_path.is_absolute())
            self.assertEqual("payloads", relative_path.parts[0])

            payload_path = (CORPUS_ROOT / relative_path).resolve(strict=True)
            self.assertTrue(payload_path.is_relative_to(PAYLOADS_ROOT))
            payload = payload_path.read_bytes()
            self.assertEqual(sample["byte_count"], len(payload))
            self.assertEqual(sample["sha256"], hashlib.sha256(payload).hexdigest())

    def test_manifest_is_canonical_compact_json_and_checksum_matches(self):
        manifest = load_manifest()
        canonical = json.dumps(
            manifest,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.assertEqual(canonical, MANIFEST_PATH.read_bytes())

        checksum_parts = CHECKSUM_PATH.read_text(encoding="ascii").split()
        self.assertEqual(2, len(checksum_parts))
        self.assertEqual("bench/web-corpus/manifest.v1.json", checksum_parts[1])
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), checksum_parts[0])

    def test_stdlib_verifier_accepts_frozen_corpus(self):
        completed = run_verifier(CORPUS_ROOT.parents[1], CORPUS_ROOT)
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        self.assertIn("verified 8 samples", completed.stdout)

    def test_verifier_rejects_parent_traversal_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root, corpus_root = copy_corpus_to_temporary_repository(
                temporary_directory
            )
            escaped_payload = corpus_root / "escaped.html"
            escaped_payload.write_bytes(
                (corpus_root / "payloads" / "document.small.html").read_bytes()
            )
            manifest = json.loads(
                (corpus_root / "manifest.v1.json").read_text(encoding="utf-8")
            )
            manifest["samples"][0]["path"] = "payloads/../escaped.html"
            write_manifest_and_checksum(corpus_root, manifest)

            completed = run_verifier(repository_root, corpus_root)

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("normalized path beneath payloads/", completed.stderr)

    def test_verifier_rejects_symlink_escaping_payload_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root, corpus_root = copy_corpus_to_temporary_repository(
                temporary_directory
            )
            escaped_payload = repository_root / "escaped.html"
            escaped_payload.write_bytes(
                (corpus_root / "payloads" / "document.small.html").read_bytes()
            )
            symlink_path = corpus_root / "payloads" / "escaped.html"
            symlink_path.symlink_to(escaped_payload)
            manifest = json.loads(
                (corpus_root / "manifest.v1.json").read_text(encoding="utf-8")
            )
            manifest["samples"][0]["path"] = "payloads/escaped.html"
            write_manifest_and_checksum(corpus_root, manifest)

            completed = run_verifier(repository_root, corpus_root)

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("path escapes payloads/", completed.stderr)

    def test_verifier_rejects_unmanifested_payloads_at_any_depth(self):
        for extra_path in (
            Path("unmanifested.bin"),
            Path("nested") / "unmanifested.bin",
        ):
            with self.subTest(extra_path=extra_path):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    repository_root, corpus_root = copy_corpus_to_temporary_repository(
                        temporary_directory
                    )
                    unmanifested_payload = corpus_root / "payloads" / extra_path
                    unmanifested_payload.parent.mkdir(parents=True, exist_ok=True)
                    unmanifested_payload.write_bytes(b"not listed in manifest")

                    completed = run_verifier(repository_root, corpus_root)

                self.assertNotEqual(0, completed.returncode)
                self.assertIn("unmanifested payload paths", completed.stderr)

    def test_size_classification_includes_every_boundary_and_rejects_outliers(self):
        expected_classes = {
            1_024: "small",
            10_240: "small",
            10_241: "medium",
            262_144: "medium",
            262_145: "large",
            2_097_152: "large",
        }
        for byte_count, expected_class in expected_classes.items():
            with self.subTest(byte_count=byte_count):
                self.assertEqual(
                    expected_class,
                    VERIFIER.classify_size(byte_count),
                )

        for byte_count in (1_023, 2_097_153):
            with self.subTest(byte_count=byte_count):
                with self.assertRaises(VERIFIER.VerificationError):
                    VERIFIER.classify_size(byte_count)


if __name__ == "__main__":
    unittest.main()
