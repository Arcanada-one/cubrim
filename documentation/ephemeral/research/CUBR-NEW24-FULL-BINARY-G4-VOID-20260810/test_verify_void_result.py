#!/usr/bin/env python3
"""Regression tests for the immutable G4 VOID evidence package."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
VERIFY = PACKAGE / "verify_void_result.py"


class VoidResultVerifierTests(unittest.TestCase):
    def run_verifier(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFY), "--package", str(root)],
            check=False,
            text=True,
            capture_output=True,
        )

    def clone_package(self, parent: Path) -> Path:
        target = parent / "package"
        shutil.copytree(PACKAGE, target)
        return target

    @staticmethod
    def make_writable(path: Path) -> None:
        os.chmod(path, path.stat().st_mode | 0o200)

    def assert_named_rejection(self, result: subprocess.CompletedProcess[str], message: str) -> None:
        self.assertEqual(result.returncode, 2, result)
        self.assertNotIn("VOID / NO-SELECT", result.stdout)
        self.assertIn(message, result.stderr)

    def test_actual_package_verifies_void_no_select(self) -> None:
        result = self.run_verifier(PACKAGE)
        self.assertEqual(result.returncode, 0, result)
        self.assertEqual(result.stdout, "VOID / NO-SELECT\n")
        self.assertEqual(result.stderr, "")

    def test_result_json_is_exactly_void_without_samples_or_interpretation(self) -> None:
        result = json.loads((PACKAGE / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["verdict"]["profile_status"], "VOID")
        self.assertEqual(result["verdict"]["selection"], "NO-SELECT")
        self.assertEqual(result["campaign_boundary"]["performance_sample_count"], 0)
        self.assertEqual(result["campaign_boundary"]["performance_sample_artifact_count"], 0)
        self.assertFalse(result["publication_limits"]["performance_interpretation_performed"])

    def test_rejects_remote_content_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            path = root / "remote-evidence" / "FAILED.STAMP"
            self.make_writable(path)
            path.write_text(path.read_text(encoding="utf-8").replace("status=VOID", "status=PASS"), encoding="utf-8")
            self.assert_named_rejection(
                self.run_verifier(root), "remote evidence checksum mismatch: FAILED.STAMP"
            )

    def test_preserves_and_enforces_zero_byte_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            path = root / "remote-evidence" / "preflight" / "runner-contract-test.txt"
            self.make_writable(path)
            path.write_text("not empty\n", encoding="utf-8")
            self.assert_named_rejection(
                self.run_verifier(root),
                "remote evidence size mismatch: preflight/runner-contract-test.txt",
            )

    def test_rejects_remote_manifest_mode_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            path = root / "remote-tree-manifest.tsv"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "f\t444\t0\t0\t0\te3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\tpreflight/process-conflicts.txt",
                    "f\t644\t0\t0\t0\te3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\tpreflight/process-conflicts.txt",
                ),
                encoding="utf-8",
            )
            self.assert_named_rejection(
                self.run_verifier(root), "remote manifest mode mismatch: preflight/process-conflicts.txt"
            )

    def test_rejects_campaign_performance_sample_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            path = root / "remote-evidence" / "cells" / "dickens-max" / "perf1.data"
            self.make_writable(root / "remote-evidence")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"sample")
            self.assert_named_rejection(
                self.run_verifier(root), "campaign performance artifact present: cells/dickens-max/perf1.data"
            )

    def test_rejects_top_level_campaign_performance_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            (root / "campaign-performance.csv").write_text("sample\n", encoding="utf-8")
            self.assert_named_rejection(
                self.run_verifier(root), "prohibited package artifact present: campaign-performance.csv"
            )

    def test_rejects_top_level_authoritative_completion_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            (root / "TIMING-DONE.STAMP").write_text("done\n", encoding="utf-8")
            self.assert_named_rejection(
                self.run_verifier(root), "prohibited package artifact present: TIMING-DONE.STAMP"
            )

    def test_rejects_top_level_campaign_cell_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            path = root / "cells" / "dickens-max" / "perf1.data"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"sample")
            self.assert_named_rejection(
                self.run_verifier(root), "prohibited package artifact present: cells"
            )

    def test_rejects_top_level_database_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            (root / "db-upsert.sql").write_text("-- mutation\n", encoding="utf-8")
            self.assert_named_rejection(
                self.run_verifier(root), "prohibited package artifact present: db-upsert.sql"
            )

    def test_rejects_unit_invocation_or_restart_drift(self) -> None:
        for old, new, message in (
            ("InvocationID=27cba50809fb4066b8915510b33a2b30", "InvocationID=0", "unit InvocationID mismatch"),
            ("NRestarts=0", "NRestarts=1", "unit NRestarts mismatch"),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temp:
                root = self.clone_package(Path(temp))
                path = root / "unit-properties.txt"
                path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
                self.assert_named_rejection(self.run_verifier(root), message)

    def test_rejects_journal_failure_or_invocation_drift(self) -> None:
        for old, new, message in (
            (
                "runner cgroup containment control failed",
                "runner cgroup containment control passed",
                "journal failure message mismatch",
            ),
            (
                "27cba50809fb4066b8915510b33a2b30",
                "00000000000000000000000000000000",
                "journal invocation mismatch",
            ),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temp:
                root = self.clone_package(Path(temp))
                path = root / "systemd-journal.jsonl"
                path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
                self.assert_named_rejection(self.run_verifier(root), message)

    def test_rejects_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            path = root / "identities.tsv"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "main_commit\t708cda945a285526610371d812e4f54725eb6baf",
                    "main_commit\t0000000000000000000000000000000000000000",
                ),
                encoding="utf-8",
            )
            self.assert_named_rejection(self.run_verifier(root), "identity main_commit mismatch")

    def test_rejects_isolation_reproduction_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.clone_package(Path(temp))
            path = root / "local-isolation-reproduction.txt"
            path.write_text(
                path.read_text(encoding="utf-8").replace("env_set_rc=1", "env_set_rc=0"),
                encoding="utf-8",
            )
            self.assert_named_rejection(self.run_verifier(root), "isolation reproduction env_set_rc mismatch")


if __name__ == "__main__":
    unittest.main()
