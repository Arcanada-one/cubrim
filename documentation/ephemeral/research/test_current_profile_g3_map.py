#!/usr/bin/env python3
"""Unit and mutation-sensitive tests for the frozen G3 instruction mapper."""

from __future__ import annotations

import importlib.util
import dataclasses
import pathlib
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal


HERE = pathlib.Path(__file__).resolve().parent
MAPPER_PATH = HERE / "current_profile_g3_map.py"
BINARY_DSO = "/root/cubr-new24-current-profile-g3-src/target-profile/release/cubrim"


def load_mapper():
    if not MAPPER_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("current_profile_g3_map", MAPPER_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MAPPER = load_mapper()


def objdump_fixture() -> str:
    return """\
0000000000003000 <cubrim::cm2::StateMap::upd>:
    3001: 48 89 c0              mov %rax,%rax
0000000000001000 <cubrim::cm2::sm_div>:
    1000: 90                    nop
0000000000002000 <cubrim::cm2::StateMap::p12>:
    2004: 90                    nop
0000000000005000 <cubrim::cm2::Ctr::upd>:
    5000: 90                    nop
    5500: 90                    nop
    6001: 90                    nop
    7002: 90                    nop
0000000000004000 <cubrim::cm2::Ctr::predict>:
    4003: 90                    nop
0000000000004500 <cubrim::cm2::Ctr::predict>:
    4500: 90                    nop
"""


def addr2line_fixture() -> str:
    return """\
0x3001
cubrim::cm2::StateMap::upd
/src/code/cubrim-rs/src/cm2.rs:242
0x1000
cubrim::cm2::sm_div
/src/code/cubrim-rs/src/cm2.rs:98
0x7002
cubrim::cm2::Ctr::upd
/src/code/cubrim-rs/src/cm2.rs:316
0x2004
cubrim::cm2::StateMap::p12
/src/code/cubrim-rs/src/cm2.rs:236
0x5000
cubrim::cm2::Ctr::upd
/src/code/cubrim-rs/src/cm2.rs:304
0x6001
cubrim::cm2::Ctr::upd
/src/code/cubrim-rs/src/cm2.rs:315
0x4003
cubrim::cm2::Ctr::predict
/src/code/cubrim-rs/src/cm2.rs:292
0x4500
cubrim::cm2::Ctr::predict
/src/code/cubrim-rs/src/cm2.rs:296
0x5500
cubrim::cm2::Ctr::upd
/src/code/cubrim-rs/src/cm2.rs:314
"""


class MapperPresenceTest(unittest.TestCase):
    def test_mapper_exists_before_behavior_tests_run(self) -> None:
        self.assertTrue(MAPPER_PATH.is_file(), f"mapper missing: {MAPPER_PATH}")


@unittest.skipUnless(MAPPER is not None, "mapper does not exist yet")
class MapperBehaviorTest(unittest.TestCase):
    def test_filter_correlates_demangled_cm2_start_but_preserves_raw_symbols(self) -> None:
        self.assertTrue(hasattr(MAPPER, "filter_objdumps"), "objdump filter missing")
        raw = """\
0000000000001000 <_RNvRawCm2>:
    1000: 90                    nop
0000000000002000 <_RNvRawOther>:
    2000: 90                    nop
"""
        demangled = """\
0000000000001000 <<cubrim::cm2::Ctr>::upd>:
    1000: 90                    nop
0000000000002000 <cubrim::other::foo>:
    2000: 90                    nop
"""

        filtered_raw, filtered_demangled, summary = MAPPER.filter_objdumps(raw, demangled)

        self.assertIn("<_RNvRawCm2>", filtered_raw)
        self.assertNotIn("_RNvRawOther", filtered_raw)
        self.assertIn("cubrim::cm2", filtered_demangled)
        self.assertNotIn("cubrim::other", filtered_demangled)
        self.assertEqual(summary["selected_symbols"], 1)
        self.assertEqual(summary["selected_instructions"], 1)
        self.assertEqual(summary["full_raw_instructions"], 2)
        self.assertEqual(summary["full_demangled_instructions"], 2)

    def test_filter_fails_when_raw_and_demangled_symbol_starts_diverge(self) -> None:
        self.assertTrue(hasattr(MAPPER, "filter_objdumps"), "objdump filter missing")
        raw = """\
0000000000001000 <_RNvRawCm2>:
    1000: 90                    nop
"""
        demangled = """\
0000000000001001 <<cubrim::cm2::Ctr>::upd>:
    1001: 90                    nop
"""

        with self.assertRaisesRegex(MAPPER.MappingError, "symbol starts differ"):
            MAPPER.filter_objdumps(raw, demangled)

    def test_cli_filter_writes_compact_outputs_and_summary_atomically(self) -> None:
        raw = """\
0000000000001000 <_RNvRawCm2>:
    1000: 90                    nop
0000000000002000 <_RNvRawOther>:
    2000: 90                    nop
"""
        demangled = """\
0000000000001000 <<cubrim::cm2::Ctr>::upd>:
    1000: 90                    nop
0000000000002000 <cubrim::other::foo>:
    2000: 90                    nop
"""
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw_full = root / "raw-full.txt"
            demangled_full = root / "demangled-full.txt"
            raw_compact = root / "raw-compact.txt"
            demangled_compact = root / "demangled-compact.txt"
            summary = root / "summary.tsv"
            raw_full.write_text(raw, encoding="utf-8")
            demangled_full.write_text(demangled, encoding="utf-8")

            filtered = subprocess.run(
                [
                    sys.executable,
                    str(MAPPER_PATH),
                    "filter",
                    "--raw-full",
                    str(raw_full),
                    "--demangled-full",
                    str(demangled_full),
                    "--raw-output",
                    str(raw_compact),
                    "--demangled-output",
                    str(demangled_compact),
                    "--summary-output",
                    str(summary),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(filtered.returncode, 0, filtered.stderr)
            self.assertIn("<_RNvRawCm2>", raw_compact.read_text(encoding="utf-8"))
            self.assertNotIn("RawOther", raw_compact.read_text(encoding="utf-8"))
            self.assertEqual(
                summary.read_text(encoding="utf-8"),
                "metric\tvalue\n"
                "selected_symbols\t1\n"
                "selected_instructions\t1\n"
                "full_raw_symbols\t2\n"
                "full_demangled_symbols\t2\n"
                "full_raw_instructions\t2\n"
                "full_demangled_instructions\t2\n",
            )

    def test_unique_mapping_uses_frozen_buckets_and_numeric_order(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)

        self.assertEqual(
            [(row.object_address, row.bucket) for row in rows],
            [
                (0x1000, "sm_div"),
                (0x2004, "state_map_predict"),
                (0x3001, "state_map_update"),
                (0x4003, "ctr_predict_stationary"),
                (0x4500, "state_map_predict_call"),
                (0x5000, "ctr_update_stationary"),
                (0x5500, "state_map_update_call"),
                (0x6001, "ctr_next_state"),
                (0x7002, "ctr_record_store"),
            ],
        )
        self.assertEqual(rows[1].symbol_offset, "cubrim::cm2::StateMap::p12+0x4")
        self.assertEqual(rows[1].file, "/src/code/cubrim-rs/src/cm2.rs")
        self.assertEqual(rows[1].line, 236)

    def test_instruction_map_round_trip_is_byte_deterministic(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        first = MAPPER.render_instruction_map(rows)
        second = MAPPER.render_instruction_map(list(reversed(rows)))

        self.assertEqual(first, second)
        self.assertEqual(MAPPER.render_instruction_map(MAPPER.parse_instruction_map(first)), first)
        self.assertTrue(
            first.startswith(
                "object_address\tsymbol_offset\tfile\tline\ttarget_owner\tbucket\tdso\n"
            )
        )

    def test_inlined_target_frame_under_non_target_outer_owner_remains_target_owned(self) -> None:
        objdump = """\
0000000000001000 <_RNvRawOther>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
<cubrim::cm2::StateMap>::p12
/src/code/cubrim-rs/src/cm2.rs:236
cubrim::other::decode
/src/code/cubrim-rs/src/other.rs:10
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual(
            [(row.target_owner, row.bucket) for row in rows],
            [(True, "state_map_predict")],
        )

    def test_unresolved_inlined_target_frame_under_non_target_outer_is_not_dropped(self) -> None:
        objdump = """\
0000000000001000 <_RNvRawDecode>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
<cubrim::cm2::StateMap>::p12
/src/code/cubrim-rs/src/cm2.rs:?
cubrim::cm2::decode
/src/code/cubrim-rs/src/cm2.rs:900
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual(
            [(row.target_owner, row.bucket) for row in rows],
            [(True, "target_unresolved")],
        )

    def test_sm_div_inline_frame_excludes_state_map_update_caller(self) -> None:
        objdump = """\
0000000000001000 <cubrim::cm2::Ctr::upd>:
    1002: 90                    nop
"""
        decoded = """\
0x1002
cubrim::cm2::sm_div
/src/code/cubrim-rs/src/cm2.rs:99
cubrim::cm2::StateMap::upd
/src/code/cubrim-rs/src/cm2.rs:244
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual([(row.bucket, row.line) for row in rows], [("sm_div", 99)])

    def test_inlined_state_map_body_excludes_call_site_bucket(self) -> None:
        objdump = """\
0000000000001000 <cubrim::cm2::Ctr::predict>:
    1002: 90                    nop
0000000000002000 <cubrim::cm2::Ctr::upd>:
    2002: 90                    nop
"""
        decoded = """\
0x1002
cubrim::cm2::StateMap::p12
/src/code/cubrim-rs/src/cm2.rs:237
cubrim::cm2::Ctr::predict
/src/code/cubrim-rs/src/cm2.rs:296
0x2002
cubrim::cm2::StateMap::upd
/src/code/cubrim-rs/src/cm2.rs:245
cubrim::cm2::Ctr::upd
/src/code/cubrim-rs/src/cm2.rs:314
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual(
            [(row.bucket, row.line) for row in rows],
            [("state_map_predict", 237), ("state_map_update", 245)],
        )

    def test_distinct_target_frames_at_one_address_fail_overlap(self) -> None:
        objdump = """\
0000000000001000 <cubrim::cm2::Ctr::predict>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
cubrim::cm2::StateMap::p12
/src/code/cubrim-rs/src/cm2.rs:236
cubrim::cm2::StateMap::upd
/src/code/cubrim-rs/src/cm2.rs:242
"""

        with self.assertRaisesRegex(MAPPER.MappingError, "overlap"):
            MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

    def test_targeted_symbol_with_unresolved_line_is_never_reassigned(self) -> None:
        objdump = """\
0000000000001000 <cubrim::cm2::StateMap::p12>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
cubrim::cm2::StateMap::p12
??:0
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual([(row.bucket, row.line) for row in rows], [("target_unresolved", 0)])

    def test_ctr_new_outside_exact_target_union_is_other_user(self) -> None:
        objdump = """\
0000000000001000 <cubrim::cm2::Ctr::new>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
cubrim::cm2::Ctr::new
/src/code/cubrim-rs/src/cm2.rs:283
"""

        try:
            rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)
        except MAPPER.MappingError as exc:
            self.fail(f"Ctr::new is outside the exact target union: {exc}")

        self.assertEqual([(row.bucket, row.line) for row in rows], [("other_user", 283)])

    def test_call_site_lines_have_dedicated_buckets(self) -> None:
        objdump = """\
0000000000001000 <cubrim::cm2::Ctr::upd>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
cubrim::cm2::Ctr::upd
/src/code/cubrim-rs/src/cm2.rs:314
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual([(row.bucket, row.line) for row in rows], [("state_map_update_call", 314)])

    def test_malformed_object_address_fails_closed(self) -> None:
        bad = objdump_fixture().replace("    3001:", "    xyz:", 1)

        with self.assertRaisesRegex(MAPPER.MappingError, "malformed instruction address"):
            MAPPER.build_instruction_rows(bad, addr2line_fixture(), BINARY_DSO)

    def test_sample_reduction_joins_exact_dso_symbol_offset_not_runtime_ip(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        samples = """\
         3  7f1234567890 cubrim::cm2::StateMap::p12+0x4 (/root/cubr-new24-current-profile-g3-src/target-profile/release/cubrim)
         1  ffffffff81000100 [unknown] ([kernel.kallsyms])
"""

        reduced = MAPPER.reduce_perf_script(rows, samples, BINARY_DSO)

        self.assertEqual(
            [
                (item.bucket, item.sample_count, item.period, item.sum_period_squared)
                for item in reduced
                if item.period
            ],
            [("state_map_predict", 1, 3, 9), ("kernel", 1, 1, 1)],
        )
        self.assertEqual(sum(item.period for item in reduced), 4)

    def test_raw_runtime_ip_for_binary_without_symbol_offset_is_rejected(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        samples = (
            "3 7f1234567890 [unknown] "
            "(/root/cubr-new24-current-profile-g3-src/target-profile/release/cubrim)\n"
        )

        with self.assertRaisesRegex(MAPPER.MappingError, "symbol[+]offset"):
            MAPPER.reduce_perf_script(rows, samples, BINARY_DSO)

    def test_nonexact_binary_dso_is_preserved_as_other_dso(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        samples = "3 7f1234567890 cubrim::cm2::StateMap::p12+0x4 (/tmp/other-cubrim)\n"

        reduced = MAPPER.reduce_perf_script(rows, samples, BINARY_DSO)

        self.assertEqual(
            [(item.bucket, item.period) for item in reduced if item.period], [("other_dso", 3)]
        )

    def test_unmapped_exact_binary_symbol_offset_is_rejected(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        samples = (
            "3 7f1234567890 cubrim::cm2::StateMap::p12+0x99 "
            f"({BINARY_DSO})\n"
        )

        with self.assertRaisesRegex(MAPPER.MappingError, "unmapped binary sample"):
            MAPPER.reduce_perf_script(rows, samples, BINARY_DSO)

    def test_perf_symbol_with_spaces_and_generics_is_parsed_from_stable_edges(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        complex_symbol = (
            "<cubrim::cm2::StateMap as core::convert::AsRef<[u32]>>::as_ref+0x0"
        )
        complex_row = dataclasses.replace(rows[0], symbol_offset=complex_symbol)
        samples = f"7 7f1234567890 {complex_symbol} ({BINARY_DSO})\n"

        reduced = MAPPER.reduce_perf_script([complex_row], samples, BINARY_DSO)
        observed = next(item for item in reduced if item.period)

        self.assertEqual(observed.period, 7)
        self.assertEqual(observed.bucket, "sm_div")

    def test_raw_rust_symbol_key_joins_perf_while_addr2line_is_demangled(self) -> None:
        raw_symbol = "_RNvNtCs1234_6cubrim3cm28StateMap3p12"
        objdump = f"""\
0000000000001000 <{raw_symbol}>:
    1004: 90                    nop
"""
        decoded = """\
0x1004
<cubrim::cm2::StateMap>::p12
/src/code/cubrim-rs/src/cm2.rs:236
"""
        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)
        samples = f"9 7f1234567890 {raw_symbol}+0x4 ({BINARY_DSO})\n"

        reduced = MAPPER.reduce_perf_script(rows, samples, BINARY_DSO)

        self.assertEqual(rows[0].symbol_offset, f"{raw_symbol}+0x4")
        self.assertEqual(
            [(item.bucket, item.period) for item in reduced if item.period],
            [("state_map_predict", 9)],
        )

    def test_raw_target_symbol_with_unresolved_demangled_frame_is_bucketed(self) -> None:
        raw_symbol = "_RNvNtCs1234_6cubrim3cm28StateMap3p12"
        objdump = f"""\
0000000000001000 <{raw_symbol}>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
<cubrim::cm2::StateMap>::p12
??:?
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual([(row.bucket, row.file, row.line) for row in rows], [("target_unresolved", "??", 0)])

    def test_unresolved_non_target_addr2line_sentinel_is_other_user(self) -> None:
        raw_symbol = "_RNvNtCs1234_6cubrim3cm23Foo3bar"
        objdump = f"""\
0000000000001000 <{raw_symbol}>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
cubrim::cm2::Foo::bar
??:?
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual([(row.bucket, row.file, row.line) for row in rows], [("other_user", "??", 0)])

    def test_unknown_line_on_library_path_is_other_user_line_zero(self) -> None:
        objdump = """\
0000000000001000 <_RNvRawAlloc>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
alloc::raw_vec::RawVec::grow
/rustc/abc/library/alloc/src/raw_vec/mod.rs:?
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual(
            [(row.bucket, row.file, row.line) for row in rows],
            [("other_user", "/rustc/abc/library/alloc/src/raw_vec/mod.rs", 0)],
        )

    def test_unknown_line_on_target_cm2_frame_is_target_unresolved(self) -> None:
        objdump = """\
0000000000001000 <_RNvRawStateMap>:
    1000: 90                    nop
"""
        decoded = """\
0x1000
<cubrim::cm2::StateMap>::p12
/src/code/cubrim-rs/src/cm2.rs:?
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual(
            [(row.bucket, row.file, row.line) for row in rows],
            [("target_unresolved", "/src/code/cubrim-rs/src/cm2.rs", 0)],
        )

    def test_resolved_epilogue_owned_by_target_is_target_unresolved(self) -> None:
        objdump = """\
0000000000001000 <_RNvRawCtrUpd>:
    1000: c3                    ret
"""
        decoded = """\
0x1000
<cubrim::cm2::Ctr>::upd
/src/code/cubrim-rs/src/cm2.rs:318
"""

        rows = MAPPER.build_instruction_rows(objdump, decoded, BINARY_DSO)

        self.assertEqual([(row.bucket, row.line) for row in rows], [("target_unresolved", 318)])

    def test_map_coverage_reports_all_target_owner_instructions_once(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        unresolved = dataclasses.replace(
            rows[0], object_address=0x8000, symbol_offset="_RNvRawCtrUpd+0x8", bucket="target_unresolved"
        )

        coverage = MAPPER.map_coverage([*rows, unresolved])

        self.assertEqual(coverage["target_owner_instructions"], 10)
        self.assertEqual(coverage["assigned_target_instructions"], 10)
        self.assertEqual(coverage["target_unresolved_instructions"], 1)
        self.assertEqual(coverage["coverage_percent"], "100.000000")

    def test_map_coverage_rejects_owner_bucket_mismatch_in_both_directions(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        owner_as_residual = dataclasses.replace(rows[0], bucket="other_user")
        non_owner_as_target = dataclasses.replace(rows[0], target_owner=False)

        with self.assertRaisesRegex(MAPPER.MappingError, "target-owner instruction"):
            MAPPER.map_coverage([owner_as_residual, *rows[1:]])
        with self.assertRaisesRegex(MAPPER.MappingError, "non-owner instruction"):
            MAPPER.map_coverage([non_owner_as_target, *rows[1:]])

    def test_non_cm2_exact_binary_sample_is_other_user(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        samples = f"5 7f1234567890 _RNvNtCs1234_6cubrim5other3foo+0x7 ({BINARY_DSO})\n"

        reduced = MAPPER.reduce_perf_script(rows, samples, BINARY_DSO)

        self.assertEqual(
            [(item.bucket, item.period) for item in reduced if item.period], [("other_user", 5)]
        )

    def test_composites_are_exact_and_period_is_conserved(self) -> None:
        self.assertTrue(hasattr(MAPPER, "composite_shares"), "composite reducer missing")
        shares = [
            MAPPER.BucketShare("state_map_predict", 10, 100),
            MAPPER.BucketShare("state_map_predict_call", 2, 100),
            MAPPER.BucketShare("state_map_update", 20, 100),
            MAPPER.BucketShare("state_map_update_call", 3, 100),
            MAPPER.BucketShare("sm_div", 5, 100),
            MAPPER.BucketShare("ctr_update_stationary", 30, 100),
            MAPPER.BucketShare("ctr_next_state", 4, 100),
            MAPPER.BucketShare("ctr_record_store", 1, 100),
            MAPPER.BucketShare("other_user", 25, 100),
        ]

        composites = MAPPER.composite_shares(shares)

        self.assertEqual(composites["state_map_total"], Decimal("0.40"))
        self.assertEqual(composites["whole_update"], Decimal("0.63"))
        MAPPER.validate_period_conservation(shares)

    def test_reduction_retains_weighted_sample_moments_per_bucket(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        symbol = "cubrim::cm2::StateMap::p12+0x4"
        samples = f"3 7f1 {symbol} ({BINARY_DSO})\n4 7f2 {symbol} ({BINARY_DSO})\n"

        reduced = MAPPER.reduce_perf_script(rows, samples, BINARY_DSO)
        target = next(item for item in reduced if item.bucket == "state_map_predict")

        self.assertEqual(target.sample_count, 2)
        self.assertEqual(target.period, 7)
        self.assertEqual(target.sum_period_squared, 25)

    def test_record_diagnostics_classify_supported_refuted_and_indeterminate(self) -> None:
        supported = [MAPPER.BucketShare("state_map_predict", 4787, 4787, 4787, 4787)]
        insufficient = [MAPPER.BucketShare("state_map_predict", 4786, 4786, 4786, 4786)]
        unresolved = [
            MAPPER.BucketShare("state_map_predict", 4787, 4788, 4787, 4787),
            MAPPER.BucketShare("target_unresolved", 1, 4788, 1, 1),
        ]

        self.assertEqual(MAPPER.record_diagnostics(supported, 0)["candidate_gate"], "SUPPORTED")
        self.assertEqual(
            MAPPER.record_diagnostics(insufficient, 0)["candidate_gate"], "INDETERMINATE"
        )
        self.assertEqual(MAPPER.record_diagnostics(supported, 1)["candidate_gate"], "INDETERMINATE")
        self.assertEqual(MAPPER.record_diagnostics(unresolved, 0)["candidate_gate"], "REFUTED")

    def test_lost_record_is_retained_as_indeterminate_diagnostic(self) -> None:
        rows = MAPPER.build_instruction_rows(objdump_fixture(), addr2line_fixture(), BINARY_DSO)
        symbol = "cubrim::cm2::StateMap::p12+0x4"
        samples = f"3 7f1 {symbol} ({BINARY_DSO})\nPERF_RECORD_LOST 4\n"

        _shares, diagnostics = MAPPER.reduce_perf_script_with_diagnostics(
            rows, samples, BINARY_DSO
        )

        self.assertEqual(diagnostics["lost_record_count"], 1)
        self.assertEqual(diagnostics["candidate_gate"], "INDETERMINATE")

    def test_period_conservation_rejects_missing_weight(self) -> None:
        self.assertTrue(
            hasattr(MAPPER, "validate_period_conservation"),
            "period-conservation validator missing",
        )
        shares = [
            MAPPER.BucketShare("state_map_predict", 40, 100),
            MAPPER.BucketShare("other_user", 50, 100),
        ]

        with self.assertRaisesRegex(MAPPER.MappingError, "period conservation"):
            MAPPER.validate_period_conservation(shares)

    def test_two_record_stability_accepts_one_point_and_rejects_two(self) -> None:
        self.assertTrue(hasattr(MAPPER, "verify_share_stability"), "stability verifier missing")
        first = [
            MAPPER.BucketShare("state_map_predict", 20, 100),
            MAPPER.BucketShare("other_user", 80, 100),
        ]
        at_boundary = [
            MAPPER.BucketShare("state_map_predict", 21, 100),
            MAPPER.BucketShare("other_user", 79, 100),
        ]
        over_boundary = [
            MAPPER.BucketShare("state_map_predict", 22, 100),
            MAPPER.BucketShare("other_user", 78, 100),
        ]

        deltas = MAPPER.verify_share_stability(first, at_boundary, Decimal("1.00"))
        self.assertEqual(deltas["state_map_predict"], Decimal("1.00"))
        with self.assertRaisesRegex(MAPPER.MappingError, "share instability"):
            MAPPER.verify_share_stability(first, over_boundary, Decimal("1.00"))

    def test_cli_compare_classifies_one_point_boundary_without_aborting(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            first_path = root / "first.tsv"
            boundary_path = root / "boundary.tsv"
            unstable_path = root / "unstable.tsv"
            output_path = root / "stability.tsv"
            first_path.write_text(
                MAPPER.render_bucket_shares(
                    [
                        MAPPER.BucketShare("state_map_predict", 20, 100),
                        MAPPER.BucketShare("other_user", 80, 100),
                    ]
                ),
                encoding="utf-8",
            )
            boundary_path.write_text(
                MAPPER.render_bucket_shares(
                    [
                        MAPPER.BucketShare("state_map_predict", 21, 100),
                        MAPPER.BucketShare("other_user", 79, 100),
                    ]
                ),
                encoding="utf-8",
            )
            unstable_path.write_text(
                MAPPER.render_bucket_shares(
                    [
                        MAPPER.BucketShare("state_map_predict", 22, 100),
                        MAPPER.BucketShare("other_user", 78, 100),
                    ]
                ),
                encoding="utf-8",
            )

            boundary = subprocess.run(
                [
                    sys.executable,
                    str(MAPPER_PATH),
                    "compare",
                    "--first",
                    str(first_path),
                    "--second",
                    str(boundary_path),
                    "--max-percentage-points",
                    "1.00",
                    "--output",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(boundary.returncode, 0, boundary.stderr)
            self.assertIn("classification\tshare-stable", output_path.read_text(encoding="utf-8"))

            output_path.unlink()
            unstable = subprocess.run(
                [
                    sys.executable,
                    str(MAPPER_PATH),
                    "compare",
                    "--first",
                    str(first_path),
                    "--second",
                    str(unstable_path),
                    "--max-percentage-points",
                    "1.00",
                    "--output",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(unstable.returncode, 0, unstable.stderr)
            self.assertIn("classification\tshare-unstable", output_path.read_text(encoding="utf-8"))

    def test_cli_build_and_reduce_match_library_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            objdump = root / "objdump.txt"
            decoded = root / "addr2line.txt"
            map_path = root / "instruction-map.tsv"
            coverage_path = root / "instruction-map-coverage.tsv"
            samples = root / "perf-script.txt"
            shares = root / "bucket-shares.tsv"
            diagnostics = root / "record-diagnostics.tsv"
            objdump.write_text(objdump_fixture(), encoding="utf-8")
            decoded.write_text(addr2line_fixture(), encoding="utf-8")
            samples.write_text(
                "3 7f1234567890 cubrim::cm2::StateMap::p12+0x4 "
                f"({BINARY_DSO})\n",
                encoding="utf-8",
            )

            build = subprocess.run(
                [
                    sys.executable,
                    str(MAPPER_PATH),
                    "build",
                    "--objdump",
                    str(objdump),
                    "--addr2line",
                    str(decoded),
                    "--binary-dso",
                    BINARY_DSO,
                    "--output",
                    str(map_path),
                    "--coverage-output",
                    str(coverage_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stderr)

            reduce = subprocess.run(
                [
                    sys.executable,
                    str(MAPPER_PATH),
                    "reduce",
                    "--map",
                    str(map_path),
                    "--perf-script",
                    str(samples),
                    "--binary-dso",
                    BINARY_DSO,
                    "--output",
                    str(shares),
                    "--diagnostics-output",
                    str(diagnostics),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(reduce.returncode, 0, reduce.stderr)
            parsed = MAPPER.parse_bucket_shares(shares.read_text(encoding="utf-8"))
            self.assertEqual(
                [(item.bucket, item.sample_count, item.period, item.sum_period_squared)
                 for item in parsed if item.period],
                [("state_map_predict", 1, 3, 9)],
            )
            self.assertIn("coverage_percent\t100.000000", coverage_path.read_text(encoding="utf-8"))
            self.assertIn("candidate_gate\tINDETERMINATE", diagnostics.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
