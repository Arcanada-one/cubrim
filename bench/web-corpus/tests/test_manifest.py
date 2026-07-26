import hashlib
import json
import subprocess
import sys
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


def load_manifest():
    if not MANIFEST_PATH.is_file():
        raise AssertionError(f"missing manifest: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


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
        completed = subprocess.run(
            [sys.executable, str(CORPUS_ROOT / "verify_manifest.py"), "--check"],
            cwd=CORPUS_ROOT.parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        self.assertIn("verified 8 samples", completed.stdout)


if __name__ == "__main__":
    unittest.main()
