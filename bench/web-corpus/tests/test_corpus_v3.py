"""Corpus v3: v2 plus the WebAssembly sample its gap list was waiting for.

v2 recorded WASM as a gap "blocked_on: CUBR-0077", reasoning that Cubrim does
not build for wasm32-unknown-unknown. That was true of the whole `cubrim`
crate — `ureq`, `dirs`, `rpassword`, `walkdir`, `rand` are CLI and archive
dependencies — and never of a decoder, which uses none of them. CUBR-0077
shipped, `cubrim-web-decoder` builds for wasm32 on every CI run, and the gap
closes with our own artefact rather than a generated fixture.

The assertions that matter here are the ones about *not* disturbing anything:
v2 must remain byte-for-byte what it was, because measurements are cited against
its hash.
"""

import hashlib
import json
import unittest
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[1]
V2 = CORPUS / "manifest.v2.json"
V3 = CORPUS / "manifest.v3.json"

# The hash summarize.py pinned as canonical before v3 existed. If v2 is ever
# edited, every figure published against it silently changes meaning.
V2_SHA256_AT_V3_CREATION = "fecc83c1e6559d361d0029024393a3cc98909f0c45dea3a2f0c4f11b75a3a2bf"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class CorpusV2IsFrozenTests(unittest.TestCase):
    def test_v2_manifest_is_unchanged_by_the_arrival_of_v3(self):
        digest = hashlib.sha256(V2.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            V2_SHA256_AT_V3_CREATION,
            "manifest.v2.json changed — every measurement cited against its hash "
            "now refers to a corpus that no longer exists",
        )


class CorpusV3ShapeTests(unittest.TestCase):
    def setUp(self):
        self.v2 = _load(V2)
        self.v3 = _load(V3)

    def test_v3_is_a_strict_superset_of_v2(self):
        v2_by_id = {s["sample_id"]: s for s in self.v2["samples"]}
        v3_by_id = {s["sample_id"]: s for s in self.v3["samples"]}
        self.assertTrue(set(v2_by_id) < set(v3_by_id))
        for sample_id, sample in v2_by_id.items():
            self.assertEqual(
                sample,
                v3_by_id[sample_id],
                f"{sample_id} was altered on the way into v3; carried-over samples "
                "must be identical, not merely present",
            )

    def test_v3_adds_exactly_the_wasm_sample(self):
        added = {s["sample_id"] for s in self.v3["samples"]} - {
            s["sample_id"] for s in self.v2["samples"]
        }
        self.assertEqual(added, {"wasm-medium-cubrim-decoder-v3"})

    def test_the_wasm_gap_is_closed_and_svg_is_still_open(self):
        families = {g["media_family"] for g in self.v3["gaps"]}
        self.assertNotIn("wasm", families)
        self.assertIn(
            "svg",
            families,
            "svg waits on a sourcing decision, not a dissolved technical claim — "
            "closing it silently would misrepresent the corpus",
        )

    def test_every_sample_digest_and_size_match_the_bytes_on_disk(self):
        for sample in self.v3["samples"]:
            with self.subTest(sample=sample["sample_id"]):
                payload = CORPUS / sample["path"]
                raw = payload.read_bytes()
                self.assertEqual(len(raw), sample["byte_count"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), sample["sha256"])

    def test_every_sample_is_redistributable_with_a_known_licence(self):
        # The corpus policy is that only payloads with verified redistribution
        # rights are included; an unrecognised licence id would slip past a
        # boolean-only check.
        known = {"MIT", "OFL-1.1", "proprietary-arcanada-redistributable"}
        for sample in self.v3["samples"]:
            with self.subTest(sample=sample["sample_id"]):
                self.assertTrue(sample["redistributable"])
                self.assertIn(sample["license_id"], known)

    def test_the_corpus_covers_wasm_among_its_media_families(self):
        families = {s["media_family"] for s in self.v3["samples"]}
        self.assertIn("wasm", families)


class WasmSampleTests(unittest.TestCase):
    def setUp(self):
        self.sample = next(
            s
            for s in _load(V3)["samples"]
            if s["sample_id"] == "wasm-medium-cubrim-decoder-v3"
        )
        self.raw = (CORPUS / self.sample["path"]).read_bytes()

    def test_the_payload_is_a_real_webassembly_module(self):
        # A file named .wasm that is not a module would make the corpus claim
        # coverage it does not have.
        self.assertEqual(self.raw[:4], b"\x00asm", "missing wasm magic")
        self.assertEqual(self.raw[4:8], b"\x01\x00\x00\x00", "not wasm version 1")

    def test_it_is_declared_as_wasm_with_the_right_media_type(self):
        self.assertEqual(self.sample["media_family"], "wasm")
        self.assertEqual(self.sample["media_type"], "application/wasm")

    def test_the_source_reference_names_a_build_that_can_be_repeated(self):
        source_ref = self.sample["source_ref"]
        self.assertIn("cubrim-web-decoder", source_ref)
        self.assertIn("wasm32-unknown-unknown", source_ref)

    def test_it_lands_in_a_size_class_the_corpus_already_uses(self):
        self.assertIn(self.sample["size_class"], {"small", "medium", "large"})


if __name__ == "__main__":
    unittest.main()
