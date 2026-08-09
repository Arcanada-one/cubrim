#!/usr/bin/env python3
"""Deterministic tests for the NEW-24 G3 evidence reducer."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import current_profile_g3_results as g3


RAW = HERE / "CUBR-NEW24-CURRENT-PROFILE-G3-RESULTS-20260809"
G2 = HERE / "CUBR-DECODE-ATTRIB-G2-RESULTS-20260809" / "analysis" / "result.json"
ANALYSIS = HERE / "CUBR-NEW24-CURRENT-PROFILE-G3-ANALYSIS-20260809"


def independent_tree_identity(root: Path) -> tuple[int, str, str]:
    paths = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    path_hash = hashlib.sha256("".join(f"{rel}\n" for rel in paths).encode("utf-8"))
    manifest = "".join(
        f"{hashlib.sha256((root / rel).read_bytes()).hexdigest()}  ./{rel}\n"
        for rel in paths
    ).encode("utf-8")
    content_hash = hashlib.sha256(manifest)
    return len(paths), content_hash.hexdigest(), path_hash.hexdigest()


def write_terminal(path: Path, raw: Path = RAW, **changes: object) -> None:
    count, content_digest, path_digest = independent_tree_identity(raw)
    values: dict[str, object] = {
        "schema": "current-profile-g3-terminal-observation-v1",
        "unit": "cubr-new24-current-profile-g3-20260809.service",
        "invocation_id": "049ef5caefa44ee19dad8b6da03f6a19",
        "start_utc": "2026-08-09T19:58:29Z",
        "exit_utc": "2026-08-09T20:39:15Z",
        "systemd_terminal": "Deactivated successfully",
        "service_type": "exec",
        "restart_policy": "no",
        "runtime_max": "4h5m",
        "nrestarts": 0,
        "nrestarts_observation": "live-start-and-read-only-polling-through-terminal",
        "load_state_after_gc": "not-found",
        "active_state_after": "inactive",
        "sub_state_after": "dead",
        "final_output": "/root/cubr-new24-current-profile-g3-20260809",
        "final_output_present": "true",
        "partial_output_absent": "true",
        "post_run_orphan_count": 0,
        "raw_file_count": count,
        "raw_source_content_digest": content_digest,
        "raw_destination_content_digest": content_digest,
        "raw_source_path_digest": path_digest,
        "raw_destination_path_digest": path_digest,
        "raw_manifest_entries": 206,
        "raw_manifest_exclusions": "SHA256SUMS,TIMING-DONE.STAMP",
        "raw_manifest_check": "PASS",
        "raw_tree_symlinks": 0,
        "raw_tree_writable_entries": 0,
    }
    values.update(changes)
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")


class ManifestTests(unittest.TestCase):
    def test_actual_manifest_is_exhaustive_and_valid(self) -> None:
        result = g3.validate_manifest(RAW)
        self.assertEqual(result["entries"], 206)
        self.assertEqual(result["raw_file_count"], 208)

    def test_manifest_detects_content_mutation_and_unlisted_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("alpha\n", encoding="utf-8")
            digest = hashlib.sha256((root / "a.txt").read_bytes()).hexdigest()
            (root / "SHA256SUMS").write_text(f"{digest}  ./a.txt\n", encoding="utf-8")
            (root / "TIMING-DONE.STAMP").write_text("done\n", encoding="utf-8")
            self.assertEqual(g3.validate_manifest(root)["entries"], 1)
            (root / "a.txt").write_text("mutated\n", encoding="utf-8")
            with self.assertRaisesRegex(g3.EvidenceError, "checksum mismatch"):
                g3.validate_manifest(root)
            (root / "a.txt").write_text("alpha\n", encoding="utf-8")
            (root / "extra.txt").write_text("unlisted\n", encoding="utf-8")
            with self.assertRaisesRegex(g3.EvidenceError, "manifest path set mismatch"):
                g3.validate_manifest(root)

    def test_manifest_accepts_writable_checkout_when_bytes_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "a.txt"
            data.write_text("alpha\n", encoding="utf-8")
            data.chmod(0o644)
            digest = hashlib.sha256(data.read_bytes()).hexdigest()
            (root / "SHA256SUMS").write_text(f"{digest}  ./a.txt\n", encoding="utf-8")
            (root / "TIMING-DONE.STAMP").write_text("done\n", encoding="utf-8")
            self.assertEqual(g3.validate_manifest(root)["entries"], 1)

    def test_manifest_rejects_directory_and_broken_symlinks(self) -> None:
        for broken in (False, True):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                data = root / "a.txt"
                data.write_text("alpha\n", encoding="utf-8")
                digest = hashlib.sha256(data.read_bytes()).hexdigest()
                (root / "SHA256SUMS").write_text(f"{digest}  ./a.txt\n", encoding="utf-8")
                (root / "TIMING-DONE.STAMP").write_text("done\n", encoding="utf-8")
                target = root / "missing" if broken else root / "real-dir"
                if not broken:
                    target.mkdir()
                (root / "linked-dir").symlink_to(target, target_is_directory=True)
                with self.assertRaisesRegex(g3.EvidenceError, "symlink"):
                    g3.validate_manifest(root)

    def test_analyze_does_not_resolve_away_raw_root_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            linked_raw = root / "raw-link"
            linked_raw.symlink_to(RAW, target_is_directory=True)
            terminal = root / "terminal.txt"
            write_terminal(terminal)
            with self.assertRaisesRegex(g3.EvidenceError, "unsafe raw directory"):
                g3.analyze(linked_raw, G2, terminal)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO creation unavailable")
    def test_manifest_rejects_fifo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "a.txt"
            data.write_text("alpha\n", encoding="utf-8")
            digest = hashlib.sha256(data.read_bytes()).hexdigest()
            (root / "SHA256SUMS").write_text(f"{digest}  ./a.txt\n", encoding="utf-8")
            (root / "TIMING-DONE.STAMP").write_text("done\n", encoding="utf-8")
            os.mkfifo(root / "unexpected.fifo")
            with self.assertRaisesRegex(g3.EvidenceError, "unsupported filesystem node"):
                g3.validate_manifest(root)


class TerminalTests(unittest.TestCase):
    def test_terminal_evidence_binds_external_exit_to_raw_tree(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "terminal.txt"
            write_terminal(path)
            terminal = g3.validate_terminal_evidence(path, RAW, "049ef5caefa44ee19dad8b6da03f6a19")
            self.assertEqual(terminal["systemd_terminal"], "Deactivated successfully")
            self.assertEqual(terminal["raw_file_count"], 208)
            self.assertEqual(terminal["raw_tree_writable_entries"], 0)

    def test_terminal_evidence_rejects_invocation_or_digest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "terminal.txt"
            write_terminal(path, invocation_id="f" * 32)
            with self.assertRaisesRegex(g3.EvidenceError, "terminal invocation_id mismatch"):
                g3.validate_terminal_evidence(path, RAW, "049ef5caefa44ee19dad8b6da03f6a19")
            write_terminal(path, raw_destination_content_digest="0" * 64)
            with self.assertRaisesRegex(g3.EvidenceError, "raw content digest mismatch"):
                g3.validate_terminal_evidence(path, RAW, "049ef5caefa44ee19dad8b6da03f6a19")


class AttributionTests(unittest.TestCase):
    def test_instruction_rows_must_be_unique_and_owner_consistent(self) -> None:
        rows = [
            {
                "object_address": "0x1",
                "symbol_offset": "target+0x0",
                "target_owner": "true",
                "bucket": "state_map_update",
                "dso": "/x/cubrim",
            },
            {
                "object_address": "0x2",
                "symbol_offset": "other+0x0",
                "target_owner": "false",
                "bucket": "other_user",
                "dso": "/x/cubrim",
            },
        ]
        summary = g3.validate_map_rows(rows)
        self.assertEqual(summary["target_owner_instructions"], 1)
        duplicate = rows + [dict(rows[0])]
        with self.assertRaisesRegex(g3.EvidenceError, "duplicate object_address"):
            g3.validate_map_rows(duplicate)
        wrong_owner = [dict(rows[0], target_owner="false")]
        with self.assertRaisesRegex(g3.EvidenceError, "non-owner instruction assigned"):
            g3.validate_map_rows(wrong_owner)

    def test_actual_instruction_map_has_exact_coverage(self) -> None:
        summary = g3.validate_instruction_map(RAW)
        self.assertEqual(summary["target_owner_instructions"], 429)
        self.assertEqual(summary["assigned_target_instructions"], 429)
        self.assertEqual(summary["target_unresolved_instructions"], 16)
        self.assertEqual(summary["coverage_percent"], 100.0)

    def test_namespace_mismatch_is_detected_without_reattribution(self) -> None:
        map_keys = {("/x/cubrim", "_ZN6cubrim3cm23Ctr3upd17h123E+0x17e")}
        sample_keys = {("/x/cubrim", "cubrim::cm2::Ctr::upd+0x17e")}
        audit = g3.audit_join_key_sets(map_keys, sample_keys)
        self.assertEqual(audit["status"], "FAIL")
        self.assertEqual(audit["reason_code"], "PERF_MAP_SYMBOL_NAMESPACE_MISMATCH")
        self.assertEqual(audit["exact_join_key_intersection_count"], 0)

    def test_exact_join_key_control_is_not_mislabeled(self) -> None:
        exact = ("/x/cubrim", "_ZN6cubrim3cm23Ctr3upd17h123E+0x17e")
        audit = g3.audit_join_key_sets({exact}, {exact})
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["exact_join_key_intersection_count"], 1)

    def test_symbol_namespace_mutation_flips_exact_join_to_failure(self) -> None:
        mangled = ("/x/cubrim", "_ZN6cubrim3cm23Ctr3upd17h123E+0x17e")
        self.assertEqual(g3.audit_join_key_sets({mangled}, {mangled})["status"], "PASS")
        demangled = ("/x/cubrim", "cubrim::cm2::Ctr::upd+0x17e")
        mutated = g3.audit_join_key_sets({mangled}, {demangled})
        self.assertEqual(mutated["status"], "FAIL")
        self.assertEqual(mutated["reason_code"], "PERF_MAP_SYMBOL_NAMESPACE_MISMATCH")

    def test_actual_six_perf_scripts_have_zero_exact_map_intersection(self) -> None:
        audit = g3.audit_perf_map_namespace(RAW)
        self.assertEqual(audit["status"], "FAIL")
        self.assertEqual(audit["perf_record_count"], 6)
        self.assertGreater(audit["perf_exact_binary_sample_rows"], 0)
        self.assertGreater(audit["map_mangled_join_key_count"], 0)
        self.assertGreater(audit["perf_demangled_join_key_count"], 0)
        self.assertEqual(audit["exact_join_key_intersection_count"], 0)


class StatisticalGateTests(unittest.TestCase):
    def test_candidate_gate_distinguishes_refuted_indeterminate_supported(self) -> None:
        self.assertEqual(
            g3.classify_candidate_gate(
                lost=0, target_count=5000, target_period=5000, target_period_squared=5000,
                unresolved_count=1, unresolved_period=1,
            )["status"],
            "REFUTED",
        )
        zero = g3.classify_candidate_gate(
            lost=0, target_count=0, target_period=0, target_period_squared=0,
            unresolved_count=0, unresolved_period=0,
        )
        self.assertEqual(zero["status"], "INDETERMINATE")
        self.assertIsNone(zero["effective_sample_size"])
        supported = g3.classify_candidate_gate(
            lost=0, target_count=5000, target_period=5000, target_period_squared=5000,
            unresolved_count=0, unresolved_period=0,
        )
        self.assertEqual(supported["status"], "SUPPORTED")
        self.assertGreaterEqual(supported["effective_sample_size"], 4787)
        self.assertLessEqual(supported["simultaneous_upper_bound"], 0.001)

    def test_thresholds_are_inclusive(self) -> None:
        self.assertEqual(g3.cycle_class(100.0, 90.0), "cycle-agreement")
        self.assertEqual(g3.g3_class(1.0, 1.10), "instrument-clean")
        self.assertTrue(g3.share_stable(0.10, 0.11))


class ActualEvidenceTests(unittest.TestCase):
    def test_actual_evidence_reduces_to_void_no_select(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            terminal = Path(td) / "terminal.txt"
            write_terminal(terminal)
            result = g3.analyze(RAW, G2, terminal)
        self.assertEqual(result["verdict"]["profile_status"], "VOID")
        self.assertEqual(result["verdict"]["selection"], "NO-SELECT")
        self.assertEqual(
            {key: value["status"] for key, value in result["predictions"].items()},
            {key: "NOT-EVALUATED" for key in ("P1", "P2", "P3", "P4", "P5")},
        )
        self.assertTrue(all(not row["admissible"] for row in result["predictions"].values()))
        self.assertNotIn("cells", result)
        self.assertEqual(result["provenance"]["join_namespace_audit"]["exact_join_key_intersection_count"], 0)

    def test_rendered_outputs_are_deterministic_and_ban_cross_file_reductions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "analysis"
            out.mkdir()
            terminal = out / "terminal-observation.txt"
            write_terminal(terminal)
            result = g3.analyze(RAW, G2, terminal)
            g3.write_outputs(result, out)
            first = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
            g3.write_outputs(result, out)
            second = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
            self.assertEqual(first, second)
            joined = b"\n".join(first.values()).lower()
            for banned in (b"geomean", b"geometric_mean", b"mib/s", b"corpus_mean", b"miss_stall"):
                self.assertNotIn(banned, joined)
            self.assertEqual(set(first), {"result.json", "join-namespace-audit.tsv", "predictions.tsv", "SHA256SUMS", "terminal-observation.txt"})
            self.assertIn(b"  terminal-observation.txt\n", first["SHA256SUMS"])
            self.assertNotIn(b"bucket", first["predictions.tsv"].lower())


class OutputSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads((ANALYSIS / "result.json").read_text(encoding="utf-8"))

    def seed_output(self, output: Path) -> None:
        output.mkdir()
        (output / "terminal-observation.txt").write_bytes(
            (ANALYSIS / "terminal-observation.txt").read_bytes()
        )

    def test_output_dir_symlink_is_rejected_in_write_and_check_modes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "real"
            self.seed_output(real)
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            for check in (False, True):
                with self.subTest(check=check), self.assertRaisesRegex(g3.EvidenceError, "output directory"):
                    g3.write_outputs(self.result, linked, check=check)

    def test_expected_and_foreign_symlinks_are_rejected_in_both_modes(self) -> None:
        for check in (False, True):
            with self.subTest(kind="expected", check=check), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                output = root / "analysis"
                self.seed_output(output)
                victim = root / "victim"
                victim.write_bytes(g3.rendered_outputs(self.result)["result.json"])
                (output / "result.json").symlink_to(victim)
                with self.assertRaisesRegex(g3.EvidenceError, "symlink"):
                    g3.write_outputs(self.result, output, check=check)
                self.assertEqual(victim.read_bytes(), g3.rendered_outputs(self.result)["result.json"])
            with self.subTest(kind="foreign", check=check), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                output = root / "analysis"
                self.seed_output(output)
                (output / "foreign").symlink_to(root / "missing")
                with self.assertRaisesRegex(g3.EvidenceError, "symlink"):
                    g3.write_outputs(self.result, output, check=check)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO creation unavailable")
    def test_foreign_fifo_is_rejected_in_write_and_check_modes(self) -> None:
        for check in (False, True):
            with self.subTest(check=check), tempfile.TemporaryDirectory() as td:
                output = Path(td) / "analysis"
                self.seed_output(output)
                os.mkfifo(output / "foreign.fifo")
                with self.assertRaisesRegex(g3.EvidenceError, "unsupported filesystem node"):
                    g3.write_outputs(self.result, output, check=check)

    def test_predictable_temp_symlink_cannot_touch_external_victim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "analysis"
            self.seed_output(output)
            victim = root / "victim"
            victim.write_bytes(b"DO-NOT-TOUCH\n")
            (output / ".result.json.tmp").symlink_to(victim)
            with self.assertRaisesRegex(g3.EvidenceError, "symlink"):
                g3.write_outputs(self.result, output)
            self.assertEqual(victim.read_bytes(), b"DO-NOT-TOUCH\n")

    def test_random_exclusive_temp_is_cleaned_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "analysis"
            self.seed_output(output)
            sources: list[Path] = []

            def fail_replace(source: object, destination: object) -> None:
                sources.append(Path(source))
                raise OSError("injected replace failure")

            with mock.patch.object(g3.os, "replace", side_effect=fail_replace):
                with self.assertRaisesRegex(OSError, "injected replace failure"):
                    g3.atomic_write_bytes(output, "result.json", b"payload")
            self.assertEqual(len(sources), 1)
            self.assertNotEqual(sources[0].name, ".result.json.tmp")
            self.assertTrue(sources[0].name.startswith(".result.json."))
            self.assertFalse(sources[0].exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
