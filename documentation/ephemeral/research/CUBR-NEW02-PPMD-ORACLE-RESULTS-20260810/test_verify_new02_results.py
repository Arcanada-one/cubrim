#!/usr/bin/env python3
"""Contract and mutation tests for the sealed NEW-02 result package."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
VERIFIER = PACKAGE_ROOT / "verify_new02_results.py"
RAW_RUN = Path(
    "/home/dev/cubr-new02-canonical-runs/"
    "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
)
GENERATED_FILES = (
    "README.md",
    "provenance.json",
    "results.tsv",
    "effects.tsv",
    "summary.json",
    "SHA256SUMS",
)


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_new02_results", VERIFIER)
    if spec is None or spec.loader is None:
        raise AssertionError("verifier module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rewrite_sha256sums(root: Path) -> None:
    lines = []
    for name in GENERATED_FILES[:-1]:
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}\n")
    (root / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


class New02ResultPackageTests(unittest.TestCase):
    def test_cli_accepts_the_exact_sealed_package(self) -> None:
        completed = subprocess.run(
            ("python3", str(VERIFIER), "--package", str(PACKAGE_ROOT)),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("NEW02_RESULT_VERIFICATION=PASS", completed.stdout)
        self.assertIn("outcome=CHARACTERIZED_NO_SELECT", completed.stdout)

    def test_rebuild_from_exact_raw_rows_is_byte_identical(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = Path(directory) / "rebuilt"
            verifier.build_package(RAW_RUN, rebuilt)
            for name in GENERATED_FILES:
                self.assertEqual(
                    (rebuilt / name).read_bytes(),
                    (PACKAGE_ROOT / name).read_bytes(),
                    name,
                )

    def test_void_named_sibling_is_rejected_by_raw_preflight(self) -> None:
        verifier = load_verifier()
        self.assertTrue(
            hasattr(verifier, "_require_no_void_sibling"),
            "raw preflight must expose its VOID-sibling fail-closed gate",
        )
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            raw = parent / "new02-run"
            raw.mkdir()
            (parent / "new02-void.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(verifier.VerificationError, "VOID-named record"):
                verifier._require_no_void_sibling(raw)

    def test_semantics_reject_a_rehashed_cell_change(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "package"
            shutil.copytree(PACKAGE_ROOT, mutated)
            rows = (mutated / "results.tsv").read_text(encoding="utf-8").splitlines()
            fields = rows[1].split("\t")
            archive_index = rows[0].split("\t").index("archive_bytes")
            fields[archive_index] = str(int(fields[archive_index]) + 1)
            rows[1] = "\t".join(fields)
            (mutated / "results.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
            rewrite_sha256sums(mutated)
            with self.assertRaisesRegex(verifier.VerificationError, "effect delta|source row"):
                verifier.verify_package(mutated, enforce_pinned_hashes=False)

    def test_semantics_reject_a_duplicate_243_cell_identity(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "package"
            shutil.copytree(PACKAGE_ROOT, mutated)
            rows_path = mutated / "results.tsv"
            lines = rows_path.read_text(encoding="utf-8").splitlines()
            lines[-1] = lines[1]
            rows_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            rewrite_sha256sums(mutated)
            with self.assertRaisesRegex(verifier.VerificationError, "ordered 243-cell grid"):
                verifier.verify_package(mutated, enforce_pinned_hashes=False)

    def test_semantics_reject_a_rehashed_effect_delta(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "package"
            shutil.copytree(PACKAGE_ROOT, mutated)
            effects_path = mutated / "effects.tsv"
            lines = effects_path.read_text(encoding="utf-8").splitlines()
            fields = lines[1].split("\t")
            delta_index = lines[0].split("\t").index("o4_to_o6_at_m16_delta_bytes")
            fields[delta_index] = str(int(fields[delta_index]) + 1)
            lines[1] = "\t".join(fields)
            effects_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            rewrite_sha256sums(mutated)
            with self.assertRaisesRegex(verifier.VerificationError, "effect delta"):
                verifier.verify_package(mutated, enforce_pinned_hashes=False)

    def test_semantics_reject_selection_or_a_posthoc_ceiling(self) -> None:
        verifier = load_verifier()
        for field, value in (("selection", "SELECT"), ("ceiling", "1.0")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                mutated = Path(directory) / "package"
                shutil.copytree(PACKAGE_ROOT, mutated)
                summary_path = mutated / "summary.json"
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                summary["verdict"][field] = value
                summary_path.write_text(
                    json.dumps(summary, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                rewrite_sha256sums(mutated)
                with self.assertRaisesRegex(verifier.VerificationError, "NO-SELECT|ceiling"):
                    verifier.verify_package(mutated, enforce_pinned_hashes=False)

    def test_semantics_require_canterbury_measurement_and_exclusion(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "package"
            shutil.copytree(PACKAGE_ROOT, mutated)
            effects_path = mutated / "effects.tsv"
            lines = effects_path.read_text(encoding="utf-8").splitlines()
            header = lines[0].split("\t")
            exclusion_index = header.index("excluded_from_broad_claims")
            for index in range(1, len(lines)):
                fields = lines[index].split("\t")
                if fields[header.index("relative_path")].startswith("canterbury/"):
                    fields[exclusion_index] = "false"
                    lines[index] = "\t".join(fields)
                    break
            effects_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            rewrite_sha256sums(mutated)
            with self.assertRaisesRegex(verifier.VerificationError, "Canterbury exclusion"):
                verifier.verify_package(mutated, enforce_pinned_hashes=False)

    def test_pinned_hashes_reject_rehashing_the_whole_package(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "package"
            shutil.copytree(PACKAGE_ROOT, mutated)
            readme = mutated / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            rewrite_sha256sums(mutated)
            with self.assertRaisesRegex(verifier.VerificationError, "pinned hash mismatch"):
                verifier.verify_package(mutated)


if __name__ == "__main__":
    unittest.main()
