import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

import profile_decode


class ProfileDecodeTests(unittest.TestCase):
    def test_size_bands_keep_the_64_kib_boundary_explicit(self):
        self.assertEqual(profile_decode.size_band(64 * 1024), "at-or-below-64KiB")
        self.assertEqual(profile_decode.size_band(64 * 1024 + 1), "above-64KiB")

    def test_affinity_argv_distinguishes_unpinned_and_fixed_core(self):
        self.assertEqual(profile_decode.affinity_argv("one-core"), ())
        with self.subTest(mode="fixed-core"):
            argv = profile_decode.affinity_argv("fixed-core")
            self.assertEqual(argv[-2:], ("--cpu-list", "0"))

    def test_manifest_loader_rejects_payload_hash_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload_root = root / "payloads"
            payload_root.mkdir()
            payload = b"immutable fixture"
            samples = []
            for index in range(12):
                relative = f"payloads/{index}.bin"
                (root / relative).write_bytes(payload)
                samples.append(
                    {
                        "sample_id": f"sample-{index}",
                        "path": relative,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "byte_count": len(payload),
                    }
                )
            manifest = root / "manifest.v2.json"
            manifest.write_text(
                json.dumps({"schema_version": 2, "samples": samples}),
                encoding="utf-8",
            )
            manifest_data, loaded = profile_decode.load_manifest(manifest)
            self.assertEqual(manifest_data["schema_version"], 2)
            self.assertEqual(len(loaded), 12)
            self.assertEqual(loaded[0]["size_band"], "at-or-below-64KiB")

            (root / "payloads/3.bin").write_bytes(b"changed")
            with self.assertRaisesRegex(profile_decode.ProfileBlocked, "changed"):
                profile_decode.load_manifest(manifest)

    def test_profile_record_requires_exact_round_trip_and_all_stages(self):
        valid = {
            "exact_roundtrip": True,
            "original_sha256": "a" * 64,
            "original_bytes": 10,
            "decode_profile": {
                "output_bytes": 10,
                "stages": [{"name": name, "applicable": False} for name in profile_decode.STAGE_NAMES],
                "substage_schema_version": profile_decode.SUBSTAGE_SCHEMA_VERSION,
                "substages": [
                    {
                        "name": name,
                        "parent_stage": name.split(".", 1)[0],
                        "applicable": False,
                    }
                    for name in profile_decode.SUBSTAGE_NAMES
                ],
                "model_split_schema_version": profile_decode.MODEL_SPLIT_SCHEMA_VERSION,
                "model_splits": [
                    {"name": name, "applicable": False}
                    for name in profile_decode.MODEL_SPLIT_NAMES
                ],
            },
        }
        profile_decode.validate_profile_record(
            valid,
            sample_id="sample-a",
            original_sha256="a" * 64,
            original_bytes=10,
        )
        valid["exact_roundtrip"] = False
        with self.assertRaisesRegex(profile_decode.ProfileBlocked, "round-trip"):
            profile_decode.validate_profile_record(
                valid,
                sample_id="sample-a",
                original_sha256="a" * 64,
                original_bytes=10,
            )

        valid["exact_roundtrip"] = True
        valid["decode_profile"]["substages"] = valid["decode_profile"]["substages"][:-1]
        with self.assertRaisesRegex(profile_decode.ProfileBlocked, "substage contract"):
            profile_decode.validate_profile_record(
                valid,
                sample_id="sample-a",
                original_sha256="a" * 64,
                original_bytes=10,
            )

    def test_profile_record_requires_model_split_contract(self):
        valid = {
            "exact_roundtrip": True,
            "original_sha256": "a" * 64,
            "original_bytes": 10,
            "decode_profile": {
                "output_bytes": 10,
                "stages": [{"name": name, "applicable": False} for name in profile_decode.STAGE_NAMES],
                "substage_schema_version": profile_decode.SUBSTAGE_SCHEMA_VERSION,
                "substages": [
                    {
                        "name": name,
                        "parent_stage": name.split(".", 1)[0],
                        "applicable": False,
                    }
                    for name in profile_decode.SUBSTAGE_NAMES
                ],
            },
        }
        with self.assertRaisesRegex(profile_decode.ProfileBlocked, "model split schema"):
            profile_decode.validate_profile_record(
                valid,
                sample_id="sample-a",
                original_sha256="a" * 64,
                original_bytes=10,
            )


if __name__ == "__main__":
    unittest.main()
