#!/usr/bin/env python3
"""Mutation suite for the standalone NEW-02 historical validator.

Contract proven here:

1. The real repository and the real immutable raw publication validate GREEN.
2. The validator survives `origin/main` advancing -- this is the whole reason
   the module exists, so it is asserted directly rather than assumed.
3. Every mutation below actually changes the fixture (no no-op mutants) and
   drives the validator RED.
4. The validator never imports the capture harness.

Mutations run against a writable *copy* of the raw publication; the canonical
tree is read-only and is never modified.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "verify_new02_historical.py"
REPO_ROOT = HERE.parents[3]
RAW_ROOT = Path(
    "/home/dev/cubr-new02-canonical-runs/"
    "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
)


def load_module():
    spec = importlib.util.spec_from_file_location("new02_historical_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hist = load_module()


def _make_writable_tree(destination: Path) -> Path:
    """Copy the read-only canonical tree into a writable location."""
    shutil.copytree(RAW_ROOT, destination)
    for path in [destination, *destination.rglob("*")]:
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    return destination


def _seal(root: Path) -> None:
    """Restore the read-only property the validator requires."""
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(path.stat().st_mode & ~0o222)
    root.chmod(root.stat().st_mode & ~0o222)


class RealArtefactTests(unittest.TestCase):
    """The real repository and publication must validate as they stand today."""

    def test_repository_authenticates_against_current_main(self):
        outcome = hist.authenticate_repository(REPO_ROOT)
        self.assertEqual(outcome["execution_commit"], hist.EXECUTION_COMMIT)
        self.assertEqual(outcome["execution_tree"], hist.EXECUTION_TREE)

    def test_raw_publication_validates(self):
        marker = hist.validate_raw_publication(RAW_ROOT)
        self.assertEqual(marker["status"], "COMPLETE")
        self.assertEqual(marker["observation_count"], 243)

    def test_combined_validation_passes(self):
        outcome = hist.validate_historical(REPO_ROOT, RAW_ROOT)
        self.assertEqual(outcome["HISTORICAL_VALIDATION_STATUS"], "PASS")

    def test_survives_main_having_advanced(self):
        """The defect this module repairs, asserted directly.

        `origin/main` is strictly ahead of the frozen execution commit, and the
        validator must still pass. The capture harness fails exactly here.
        """
        head = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "origin/main"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertNotEqual(
            head, hist.EXECUTION_COMMIT,
            "precondition: main must have advanced for this test to mean anything",
        )
        ahead = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor",
             hist.EXECUTION_COMMIT, "origin/main"],
            capture_output=True,
        )
        self.assertEqual(ahead.returncode, 0)
        self.assertEqual(
            hist.authenticate_repository(REPO_ROOT)["execution_commit"],
            hist.EXECUTION_COMMIT,
        )

    def test_does_not_import_the_capture_harness(self):
        """No dynamic-import machinery, and no harness module ever loaded.

        The harness path is referenced as a *string constant* so its blob can be
        authenticated at the execution commit; that is data, not a dependency.
        What must not exist is machinery that executes it.
        """
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "importlib",
            "spec_from_file_location",
            "exec_module",
            "import_module",
            "__import__",
            "import new02_oracle_grid",
            "from new02_oracle_grid",
        ):
            self.assertNotIn(
                forbidden, source,
                f"historical validator must not execute the capture harness ({forbidden})",
            )
        # The harness path may appear only as an authenticated data constant.
        self.assertEqual(
            hist.HARNESS_REPO_PATH,
            "documentation/ephemeral/research/new02_oracle_grid.py",
        )
        # Importing the validator must not pull the harness into the process.
        self.assertNotIn("new02_oracle_grid", sys.modules)

    def test_rejects_a_repository_without_the_execution_commit(self):
        with tempfile.TemporaryDirectory() as work:
            empty = Path(work) / "repo"
            empty.mkdir()
            subprocess.run(["git", "-C", str(empty), "init", "-q"], check=True)
            with self.assertRaises(hist.HistoricalValidationError):
                hist.authenticate_repository(empty)

    def test_rejects_a_non_repository(self):
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaises(hist.HistoricalValidationError):
                hist.authenticate_repository(Path(work))


class RawPublicationMutationTests(unittest.TestCase):
    """Every mutation must change bytes and drive the validator RED."""

    def _run_mutation(self, mutate):
        with tempfile.TemporaryDirectory() as work:
            # The validator pins the absolute final namespace, so a copy at a
            # different path is rejected for namespace reasons alone. Assert on
            # the sub-validators that do not depend on the namespace instead.
            tree = _make_writable_tree(Path(work) / RAW_ROOT.name)
            before = {
                p.relative_to(tree).as_posix(): p.read_bytes()
                for p in tree.rglob("*") if p.is_file()
            }
            mutate(tree)
            after = {
                p.relative_to(tree).as_posix(): p.read_bytes()
                for p in tree.rglob("*") if p.is_file()
            }
            self.assertNotEqual(before, after, "NO-OP MUTANT: fixture bytes unchanged")
            _seal(tree)
            with self.assertRaises(hist.HistoricalValidationError):
                hist.authenticated_inventory(tree)

    def test_provenance_tampering_is_rejected(self):
        def mutate(tree: Path):
            path = tree / "provenance.json"
            doc = json.loads(path.read_text())
            doc["cpu_set"] = "0-31"
            path.write_text(json.dumps(doc))
        self._run_mutation(mutate)

    def test_inventory_entry_size_tampering_is_rejected(self):
        def mutate(tree: Path):
            path = tree / "provenance.json"
            doc = json.loads(path.read_text())
            doc["inventory"][0]["size_bytes"] = 1
            path.write_text(json.dumps(doc))
        self._run_mutation(mutate)

    def test_inventory_hash_tampering_is_rejected(self):
        def mutate(tree: Path):
            path = tree / "provenance.json"
            doc = json.loads(path.read_text())
            doc["inventory"][0]["sha256"] = "0" * 64
            path.write_text(json.dumps(doc))
        self._run_mutation(mutate)

    def test_inventory_reordering_is_rejected(self):
        def mutate(tree: Path):
            path = tree / "provenance.json"
            doc = json.loads(path.read_text())
            doc["inventory"].reverse()
            path.write_text(json.dumps(doc))
        self._run_mutation(mutate)

    def test_dropped_inventory_entry_is_rejected(self):
        def mutate(tree: Path):
            path = tree / "provenance.json"
            doc = json.loads(path.read_text())
            doc["inventory"].pop()
            path.write_text(json.dumps(doc))
        self._run_mutation(mutate)


class TreeMutationTests(unittest.TestCase):
    """Structural mutations, asserted through validate_raw_publication."""

    def _expect_red(self, mutate):
        with tempfile.TemporaryDirectory() as work:
            tree = _make_writable_tree(Path(work) / RAW_ROOT.name)
            before = sorted(
                (p.relative_to(tree).as_posix(), p.stat().st_size)
                for p in tree.rglob("*") if p.is_file()
            )
            mutate(tree)
            after = sorted(
                (p.relative_to(tree).as_posix(), p.stat().st_size)
                for p in tree.rglob("*") if p.is_file()
            )
            self.assertNotEqual(before, after, "NO-OP MUTANT: tree unchanged")
            _seal(tree)
            with self.assertRaises(hist.HistoricalValidationError):
                hist.validate_raw_publication(tree)

    def test_missing_complete_marker_is_rejected(self):
        self._expect_red(lambda tree: (tree / "COMPLETE").unlink())

    def test_missing_manifest_is_rejected(self):
        self._expect_red(lambda tree: (tree / "MANIFEST.json").unlink())

    def test_missing_observations_is_rejected(self):
        self._expect_red(lambda tree: (tree / "observations.jsonl").unlink())

    def test_extra_unmanifested_file_is_rejected(self):
        self._expect_red(
            lambda tree: (tree / "cells" / "SMUGGLED.txt").write_text("x")
        )

    def test_truncated_observations_is_rejected(self):
        def mutate(tree: Path):
            path = tree / "observations.jsonl"
            lines = path.read_text().splitlines()[:-1]
            path.write_text("\n".join(lines) + "\n")
        self._expect_red(mutate)


class FrozenContractTests(unittest.TestCase):
    """The recomputed frozen contract must match the preregistered identities."""

    def test_inventory_and_grid_identities_match_the_pins(self):
        inventory = hist.authenticated_inventory(RAW_ROOT)
        self.assertEqual(len(inventory), 27)
        self.assertEqual(hist.inventory_identity(inventory), hist.SOURCE_INVENTORY_SHA256)
        self.assertEqual(hist.grid_identity(inventory), hist.SOURCE_GRID_SHA256)

    def test_grid_multiplies_to_243(self):
        inventory = hist.authenticated_inventory(RAW_ROOT)
        self.assertEqual(
            len(inventory) * len(hist.ORDERS) * len(hist.MEMORY_MIB),
            hist.OBSERVATION_COUNT,
        )

    def test_memory_exponent_matches_the_seven_zip_cap(self):
        # Large input: the requested memory governs.
        self.assertEqual(hist.expected_ppmd_memory_exponent(10_192_446, 256), 28)
        # Tiny input: 7-Zip's small-input cap governs instead.
        self.assertEqual(hist.expected_ppmd_memory_exponent(1024, 256), 16)

    def test_memory_exponent_rejects_invalid_input(self):
        with self.assertRaises(hist.HistoricalValidationError):
            hist.expected_ppmd_memory_exponent(0, 256)
        with self.assertRaises(hist.HistoricalValidationError):
            hist.expected_ppmd_memory_exponent(1024, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
