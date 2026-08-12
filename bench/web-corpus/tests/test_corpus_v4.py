"""Corpus v4: v3 plus the SVG sample its gap list was waiting on.

v3 left `svg` open deliberately — not on a technical claim like the WASM gap
before it, but on a sourcing decision. The v3 note said our own SVGs were
~300-byte inline icons, too small to say anything about a compressor. That was
true of the status and favicon sets and missed the blog diagrams, four of which
are 3.4-6.5 KB and served from arcanada.ai. The gap closes with a first-party
production asset, so there is no licence or trademark question to argue.

As with v3, the assertions that matter most are the ones about *not* disturbing
anything. v3 is the generation the published contract is pinned to
(`CANONICAL_WEB_CORPUS_MANIFEST_NAME` in cubrim-api), so a stray edit to it
would invalidate every figure measured against its hash *and* break
publication. v4 is additive and is not yet the published generation.
"""

import hashlib
import json
import unittest
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[1]
V3 = CORPUS / "manifest.v3.json"
V4 = CORPUS / "manifest.v4.json"

# The hash cubrim-api pins as CANONICAL_WEB_CORPUS_SHA256. If v3 is ever
# edited, the guarded writer rejects every bundle and every published figure
# silently refers to a corpus that no longer exists.
V3_SHA256_AT_V4_CREATION = (
    "43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5"
)

SVG_SAMPLE_ID = "svg-small-architecture-v4"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class CorpusV3IsFrozenTests(unittest.TestCase):
    def test_v3_manifest_is_unchanged_by_the_arrival_of_v4(self):
        digest = hashlib.sha256(V3.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            V3_SHA256_AT_V4_CREATION,
            "manifest.v3.json changed — cubrim-api pins this hash as the "
            "canonical corpus, so the guarded writer will now reject every "
            "bundle, and every published figure cited against it has moved",
        )


class CorpusV4ShapeTests(unittest.TestCase):
    def setUp(self):
        self.v3 = _load(V3)
        self.v4 = _load(V4)

    def test_v4_is_a_strict_superset_of_v3(self):
        v3_by_id = {s["sample_id"]: s for s in self.v3["samples"]}
        v4_by_id = {s["sample_id"]: s for s in self.v4["samples"]}
        self.assertTrue(set(v3_by_id) < set(v4_by_id))
        for sample_id, sample in v3_by_id.items():
            self.assertEqual(
                sample,
                v4_by_id[sample_id],
                f"{sample_id} was altered on the way into v4; carried-over "
                "samples must be identical, not merely present",
            )

    def test_v4_adds_exactly_the_svg_sample(self):
        added = {s["sample_id"] for s in self.v4["samples"]} - {
            s["sample_id"] for s in self.v3["samples"]
        }
        self.assertEqual(added, {SVG_SAMPLE_ID})

    def test_the_svg_gap_is_closed_and_no_gap_is_closed_silently(self):
        # v3 carried exactly one open gap (svg). v4 closes it and must not
        # invent coverage for anything else.
        self.assertEqual({g["media_family"] for g in self.v3["gaps"]}, {"svg"})
        self.assertEqual(self.v4["gaps"], [])
        self.assertIn("svg", {s["media_family"] for s in self.v4["samples"]})

    def test_the_schema_version_is_carried_over_unchanged(self):
        # A silent schema bump would be rejected downstream by the bundle
        # contract, which compares schema_version exactly.
        self.assertEqual(self.v4["schema_version"], self.v3["schema_version"])

    def test_every_sample_digest_and_size_match_the_bytes_on_disk(self):
        for sample in self.v4["samples"]:
            with self.subTest(sample=sample["sample_id"]):
                raw = (CORPUS / sample["path"]).read_bytes()
                self.assertEqual(len(raw), sample["byte_count"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), sample["sha256"])

    def test_every_sample_is_redistributable_with_a_known_licence(self):
        known = {"MIT", "OFL-1.1", "proprietary-arcanada-redistributable"}
        for sample in self.v4["samples"]:
            with self.subTest(sample=sample["sample_id"]):
                self.assertTrue(sample["redistributable"])
                self.assertIn(sample["license_id"], known)


class SvgSampleTests(unittest.TestCase):
    def setUp(self):
        self.sample = next(
            s for s in _load(V4)["samples"] if s["sample_id"] == SVG_SAMPLE_ID
        )
        self.raw = (CORPUS / self.sample["path"]).read_bytes()

    def test_the_payload_is_really_svg_and_not_a_rasterised_stand_in(self):
        text = self.raw.decode("utf-8")
        self.assertIn("<svg", text[:200])
        self.assertIn("http://www.w3.org/2000/svg", text)
        self.assertIn("</svg>", text[-200:])

    def test_it_is_declared_as_svg_with_the_right_media_type(self):
        self.assertEqual(self.sample["media_family"], "svg")
        self.assertEqual(self.sample["media_type"], "image/svg+xml")

    def test_it_is_first_party_so_redistribution_is_not_in_question(self):
        self.assertEqual(self.sample["attribution"], "Arcanada")
        self.assertEqual(
            self.sample["license_id"], "proprietary-arcanada-redistributable"
        )

    def test_the_source_reference_names_the_live_url_it_was_taken_from(self):
        # Provenance has to be re-checkable: the digest below was confirmed
        # byte-identical against the live response from arcanada.ai, and the
        # source_ref is what lets the next person repeat that check.
        source_ref = self.sample["source_ref"]
        self.assertIn("arcanada.ai", source_ref)
        self.assertIn("arcanada-architecture.svg", source_ref)
        self.assertEqual(
            hashlib.sha256(self.raw).hexdigest(),
            "c3d1bb2239da78f29c1caa6af79c3702c88693789b978bc8ed4987f1f508472b",
        )

    def test_it_is_large_enough_to_say_something_about_a_compressor(self):
        # The whole reason the v3 gap stayed open: a ~300-byte inline icon is
        # dominated by framing overhead and measures nothing.
        self.assertGreater(len(self.raw), 3000)
        self.assertEqual(self.sample["size_class"], "small")


if __name__ == "__main__":
    unittest.main()
