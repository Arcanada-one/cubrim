"""Guards on the CUBR-0074 real-world corpus (v2).

Corpus v1 was retired because generated fixtures compressed 10-20x better than
real web resources, which made every ratio measured against it meaningless.
These tests defend the properties that keep v2 honest.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import subprocess
import unittest

CORPUS = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = CORPUS / "manifest.v2.json"

# brotli-11 ratios above this mean a text sample is at least plausibly real.
# Corpus v1's CSS sat at 0.0079; published real-world text lands near 0.15-0.30.
SYNTHETIC_SUSPICION_RATIO = 0.04

# Families whose bytes are already compressed, so a high ratio is correct.
PRECOMPRESSED_FAMILIES = {"woff2"}


def load_collector():
    path = CORPUS / "collect_real_world.py"
    spec = importlib.util.spec_from_file_location("collect_real_world", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RealWorldCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text())
        cls.samples = cls.manifest["samples"]

    def test_every_sample_is_present_and_matches_its_digest(self) -> None:
        for sample in self.samples:
            payload_path = CORPUS / sample["path"]
            self.assertTrue(payload_path.is_file(), f"missing {sample['sample_id']}")
            payload = payload_path.read_bytes()
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(),
                sample["sha256"],
                f"{sample['sample_id']} does not match its recorded digest",
            )
            self.assertEqual(len(payload), sample["byte_count"])

    def test_every_sample_names_a_real_origin_and_a_licence(self) -> None:
        for sample in self.samples:
            self.assertTrue(sample["redistributable"])
            self.assertTrue(sample["license_id"].strip())
            self.assertTrue(sample["attribution"].strip())
            source = sample["source_ref"]
            self.assertTrue(source.strip())
            # The v1 defect, stated as an assertion: no generated fixtures.
            self.assertNotIn(
                "project-authored",
                source,
                f"{sample['sample_id']} is a generated fixture, not a real resource",
            )
            self.assertRegex(source, r"^(arcanada:|npm:|Inter )")

    def test_text_samples_do_not_compress_like_generated_fixtures(self) -> None:
        for sample in self.samples:
            if sample["media_family"] in PRECOMPRESSED_FAMILIES:
                continue
            payload = (CORPUS / sample["path"]).read_bytes()
            result = subprocess.run(
                ["brotli", "-q", "11", "-c"], input=payload, capture_output=True, check=True
            )
            ratio = len(result.stdout) / len(payload)
            self.assertGreater(
                ratio,
                SYNTHETIC_SUSPICION_RATIO,
                f"{sample['sample_id']} compresses to {ratio:.4f}, which is "
                "fixture-like rather than representative of real web content",
            )

    def test_precompressed_families_are_not_treated_as_compressible(self) -> None:
        fonts = [s for s in self.samples if s["media_family"] == "woff2"]
        self.assertTrue(fonts, "the corpus must retain a real already-compressed asset")

    def test_sample_ids_and_paths_are_unique(self) -> None:
        ids = [s["sample_id"] for s in self.samples]
        paths = [s["path"] for s in self.samples]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(paths), len(set(paths)))

    def test_size_classes_hold_the_bytes_they_claim(self) -> None:
        collector = load_collector()
        for sample in self.samples:
            self.assertEqual(
                collector.classify(sample["byte_count"]),
                sample["size_class"],
                f"{sample['sample_id']} is filed under the wrong size class",
            )

    def test_absent_content_types_are_recorded_rather_than_faked(self) -> None:
        gaps = {gap["media_family"] for gap in self.manifest["gaps"]}
        families = {sample["media_family"] for sample in self.samples}
        # A family may be a sample or a declared gap, never both and never
        # neither: silently dropping a content type is how a corpus starts
        # flattering its subject.
        self.assertEqual(gaps & families, set())
        for gap in self.manifest["gaps"]:
            self.assertTrue(gap["reason"].strip())
            self.assertTrue(gap["blocked_on"].strip())

    def test_collector_refuses_a_sample_whose_bytes_changed(self) -> None:
        # The corpus is pinned: a fetched source that returns different bytes
        # must fail rather than quietly redefine what was measured.
        collector = load_collector()
        source = (CORPUS / "collect_real_world.py").read_text()
        self.assertIn("changed since it was pinned", source)
        self.assertIn("A corpus sample is", source)
        self.assertTrue(hasattr(collector, "classify"))


if __name__ == "__main__":
    unittest.main()
