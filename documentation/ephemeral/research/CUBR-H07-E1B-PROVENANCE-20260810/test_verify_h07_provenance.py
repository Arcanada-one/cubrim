from __future__ import annotations

import hashlib
import json
import subprocess
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
VERIFIER = PACKAGE_DIR / "verify_h07_provenance.py"


class H07ProvenanceVerifierTests(unittest.TestCase):
    def run_verifier(self, package_dir: Path = PACKAGE_DIR) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFIER), str(package_dir)],
            check=False,
            capture_output=True,
            text=True,
        )

    def copy_package(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        package_copy = Path(temporary.name) / "package"
        shutil.copytree(PACKAGE_DIR, package_copy, ignore=shutil.ignore_patterns("__pycache__"))
        return temporary, package_copy

    def test_pristine_package_verifies(self) -> None:
        result = self.run_verifier()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("H-07 provenance package: PASS\n", result.stdout)

    def test_rejects_mutated_summary_bytes(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        summary = package_copy / "summary.json"
        summary.write_bytes(summary.read_bytes().replace(b'"H-07"', b'"H-XX"', 1))

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("summary.json SHA-256 mismatch", result.stderr)

    def test_rejects_mutated_results_bytes(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        results = package_copy / "results.tsv"
        results.write_bytes(results.read_bytes().replace(b"bitpack-fixed", b"foreign-codec", 1))

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("summary/results row 1 mismatch for mode", result.stderr)

    def test_summary_and_results_have_exact_24_row_11_field_parity(self) -> None:
        summary = json.loads((PACKAGE_DIR / "summary.json").read_text(encoding="utf-8"))
        results_bytes = (PACKAGE_DIR / "results.tsv").read_bytes()

        result = self.run_verifier()

        self.assertEqual(24, summary["n_files"])
        self.assertEqual(24, len(summary["per_file"]))
        self.assertEqual(25, results_bytes.count(b"\r\n"))
        self.assertEqual(0, result.returncode, result.stderr)

    def test_rejects_summary_value_drift_even_with_recomputed_artifact_hash(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        summary_path = package_copy / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["per_file"][0]["ratio"] += 0.5
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["sealed_e1b"]["summary"]["sha256"] = hashlib.sha256(
            summary_path.read_bytes()
        ).hexdigest()
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("summary/results row 1 mismatch for ratio", result.stderr)

    def test_rejects_summary_row_order_drift_before_hash_checks(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        summary_path = package_copy / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["per_file"][0], summary["per_file"][1] = (
            summary["per_file"][1],
            summary["per_file"][0],
        )
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("summary/results row 1 mismatch for file", result.stderr)

    def test_rejects_summary_row_unknown_field_and_bool_as_int(self) -> None:
        for label, mutation, expected in (
            (
                "unknown field",
                lambda row: row.__setitem__("selection", "GO"),
                "summary row 1 field names mismatch",
            ),
            (
                "bool as int",
                lambda row: row.__setitem__("cmp", False),
                "summary row 1 field cmp has wrong type",
            ),
        ):
            with self.subTest(label=label):
                temporary, package_copy = self.copy_package()
                self.addCleanup(temporary.cleanup)
                summary_path = package_copy / "summary.json"
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                mutation(summary["per_file"][0])
                summary_path.write_text(json.dumps(summary), encoding="utf-8")

                result = self.run_verifier(package_copy)

                self.assertNotEqual(0, result.returncode)
                self.assertIn(expected, result.stderr)

    def test_rejects_summary_row_count_and_tsv_header_order_drift(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        summary_path = package_copy / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["per_file"].pop()
        summary["n_files"] = 23
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("summary must contain exactly 24 per_file rows", result.stderr)

        temporary_2, package_copy_2 = self.copy_package()
        self.addCleanup(temporary_2.cleanup)
        results_path = package_copy_2 / "results.tsv"
        results = results_path.read_bytes()
        results_path.write_bytes(results.replace(b"corpus\tfile\ttype", b"file\tcorpus\ttype", 1))

        result = self.run_verifier(package_copy_2)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("results.tsv header mismatch", result.stderr)

    def test_results_crlf_exception_is_exact_and_scoped(self) -> None:
        results = (PACKAGE_DIR / "results.tsv").read_bytes()
        summary = (PACKAGE_DIR / "summary.json").read_bytes()
        provenance = (PACKAGE_DIR / "provenance.json").read_bytes()

        self.assertEqual(25, results.count(b"\r\n"))
        self.assertNotIn(b"\n", results.replace(b"\r\n", b""))
        self.assertNotIn(b"\r", summary)
        self.assertNotIn(b"\r", provenance)

        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        results_path = package_copy / "results.tsv"
        results_path.write_bytes(results.replace(b"\r\n", b"\n"))

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("results.tsv must retain its sealed CRLF line endings", result.stderr)

        temporary_2, package_copy_2 = self.copy_package()
        self.addCleanup(temporary_2.cleanup)
        summary_path = package_copy_2 / "summary.json"
        summary_path.write_bytes(summary.replace(b"\n", b"\r\n"))

        result = self.run_verifier(package_copy_2)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("summary.json must retain its sealed LF-only line endings", result.stderr)

    def test_rejects_crlf_provenance_and_keeps_source_files_lf_only(self) -> None:
        provenance = (PACKAGE_DIR / "provenance.json").read_bytes()
        for source_name in ("verify_h07_provenance.py", "test_verify_h07_provenance.py"):
            source = (PACKAGE_DIR / source_name).read_bytes()
            self.assertNotIn(b"\r", source, source_name)
            self.assertTrue(source.endswith(b"\n"), source_name)
        self.assertNotIn(b"\r", provenance)
        self.assertTrue(provenance.endswith(b"\n"))

        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance_path.write_bytes(provenance.replace(b"\n", b"\r\n"))

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("provenance.json must use LF-only line endings", result.stderr)

    def test_rejects_measurement_promotion(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["measured"] = True
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest must remain noncanonical, historical, and unmeasured", result.stderr)

    def test_rejects_go_promotion(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["go"] = True
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest must not assert a GO or verdict", result.stderr)

    def test_rejects_unknown_top_level_selection_go(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["selection"] = "GO"
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest schema mismatch at root", result.stderr)

    def test_rejects_unknown_nested_relink_and_promotion_semantics(self) -> None:
        mutations = (
            ("legacy_database_provenance", "promote", "H-07"),
            ("foreign_revision_discrepancy", "relink", True),
            ("implementation_base", "selection", "GO"),
            ("sealed_e1b", "verdict", "GO"),
        )
        for container, key, value in mutations:
            with self.subTest(container=container, key=key):
                temporary, package_copy = self.copy_package()
                self.addCleanup(temporary.cleanup)
                provenance_path = package_copy / "provenance.json"
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                provenance[container][key] = value
                provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

                result = self.run_verifier(package_copy)

                self.assertNotEqual(0, result.returncode)
                self.assertIn(f"manifest schema mismatch at {container}", result.stderr)

    def test_rejects_deep_manifest_extra_and_list_length_drift(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["sealed_e1b"]["summary"]["selection"] = "GO"
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest schema mismatch at sealed_e1b.summary", result.stderr)

        temporary_2, package_copy_2 = self.copy_package()
        self.addCleanup(temporary_2.cleanup)
        provenance_path = package_copy_2 / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["legacy_database_provenance"]["row_ids"].append(326)
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy_2)

        self.assertNotEqual(0, result.returncode)
        self.assertIn(
            "manifest schema mismatch at legacy_database_provenance.row_ids",
            result.stderr,
        )

    def test_rejects_manifest_bool_as_integer(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["schema_version"] = True
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest value/type mismatch at schema_version", result.stderr)

    def test_rejects_manifest_identity_drift(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["card_id"] = "FH-07"
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest identity mismatch", result.stderr)

    def test_rejects_weakened_conservative_interpretation(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["conservative_interpretation"] = "Historical evidence accepted."
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("conservative interpretation mismatch", result.stderr)

    def test_rejects_legacy_row_relinking(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["legacy_database_provenance"]["row_ids"][-1] = 326
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("legacy row provenance mismatch", result.stderr)

    def test_rejects_claimed_source_relink(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["legacy_database_provenance"]["relinking"] = "LINKED_TO_H07"
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("legacy rows must remain unrelinked", result.stderr)

    def test_rejects_legacy_core_row_hash_drift(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["legacy_database_provenance"]["core_rows_sha256"] = "0" * 64
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("legacy core-row hash mismatch", result.stderr)

    def test_rejects_foreign_revision_relabeling(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["foreign_revision_discrepancy"]["matches_h07_source_commit"] = True
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("foreign codec-revision discrepancy mismatch", result.stderr)

    def test_rejects_implementation_ancestry_drift(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["implementation_base"]["source_commit_is_ancestor"] = False
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("implementation ancestry mismatch", result.stderr)

    def test_rejects_sealed_source_metadata_drift(self) -> None:
        temporary, package_copy = self.copy_package()
        self.addCleanup(temporary.cleanup)
        provenance_path = package_copy / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["sealed_e1b"]["summary"]["sha256"] = "0" * 64
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

        result = self.run_verifier(package_copy)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("sealed E1b source metadata mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
