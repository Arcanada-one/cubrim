#!/usr/bin/env python3
"""TDD and security controls for the NEW-24 G5 full-binary mapper."""

from __future__ import annotations

import ast
import copy
import dataclasses
import gzip
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import current_profile_g5_map as g4


DSO = "/opt/cubrim"
BUILD_ID = "0123456789abcdef0123456789abcdef01234567"
LIBC_BUILD_ID = "fedcba9876543210fedcba9876543210fedcba98"
SECTION_HASH = "0" * 64
PAGE_SIZE = 4096


def sections(*rows: tuple[str, int, int, int]) -> str:
    lines = ["section\tvaddr_start\tvaddr_end\tfile_offset\tflags\tsha256"]
    for name, start, end, offset in rows:
        lines.append(f"{name}\t0x{start:x}\t0x{end:x}\t0x{offset:x}\tAX\t{SECTION_HASH}")
    return "\n".join(lines) + "\n"


def segments(*rows: tuple[str, int, int, int, int]) -> str:
    lines = [
        "segment\tvaddr_start\tvaddr_end\tfile_offset\tfile_end\talignment\tflags\tsha256"
    ]
    for name, vstart, vend, fstart, fend in rows:
        lines.append(
            f"{name}\t0x{vstart:x}\t0x{vend:x}\t0x{fstart:x}\t0x{fend:x}"
            f"\t0x1000\tR E\t{SECTION_HASH}"
        )
    return "\n".join(lines) + "\n"


OBJDUMP = """\
Disassembly of section .text:
0000000000001000 <_ZN6cubrim3foo17h0123456789abcdefE>:
    1000:\t90\t\tnop
    1001:\tc3\t\tret
"""

RESOLVER = """\
0x1000
cubrim::foo
/src/src/foo.rs:10
0x1001
cubrim::foo
/src/src/foo.rs:11
"""

PREFIXES = """\
source_domain\tpackage_identity\tprefix\treplacement
workspace\trepo:cubrim@830a9a31\t/src\t$SOURCE
rust_sysroot\trustc:31fca3ad\t/rustc\t$RUST
cargo\tcrate:example@1.0.0+checksum\t/cargo\t$CARGO
"""

READELF_PROGRAMS = """\
Elf file type is DYN (Position-Independent Executable file)
Entry point 0x1000
There are 2 program headers, starting at offset 64

Program Headers:
  Type           Offset   VirtAddr           PhysAddr           FileSiz  MemSiz   Flg Align
  LOAD           0x000000 0x0000000000000000 0x0000000000000000 0x000100 0x000100 R   0x1000
  LOAD           0x002000 0x0000000000001000 0x0000000000001000 0x000010 0x000020 R E 0x1000
"""

READELF_SECTIONS = """\
There are 3 section headers, starting at offset 0x3000:

Section Headers:
  [Nr] Name              Type            Address          Off    Size   ES Flg Lk Inf Al
  [ 0]                   NULL            0000000000000000 000000 000000 00      0   0  0
  [ 1] .text             PROGBITS        0000000000001000 002000 000010 00  AX  0   0 16
  [ 2] .data             PROGBITS        0000000000002000 003000 000008 00  WA  0   0  8
Key to Flags:
"""


def build_rows() -> list[g4.InstructionRow]:
    return g4.build_instruction_rows(
        segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010)),
        sections((".text", 0x1000, 0x1010, 0x2000)),
        OBJDUMP,
        RESOLVER,
        RESOLVER,
        PREFIXES,
        DSO,
    )


def perf_text(*samples: str, second_mmap: str = "", other_mmaps: str = "") -> str:
    mmap = (
        f"PERF_RECORD_MMAP2 10/10: [0x400000(0x1000) @ 0x2000 <{BUILD_ID}>]: "
        "r-xp /opt/cubrim\n"
    )
    if any("/lib/libc.so.6+" in sample for sample in samples) and "/lib/libc.so.6" not in other_mmaps:
        other_mmaps += (
            f"PERF_RECORD_MMAP2 10/10: [0x700000(0x1000) @ 0x0 <{LIBC_BUILD_ID}>]: "
            "r-xp /lib/libc.so.6\n"
        )
    return mmap + second_mmap + other_mmaps + "".join(f"{sample}\n" for sample in samples)


def identity() -> g4.BinaryIdentity:
    return g4.BinaryIdentity(DSO, BUILD_ID, "08:01", 12345)


def libc_snapshot() -> g4.OtherDsoSnapshot:
    return g4.OtherDsoSnapshot(
        path="/lib/libc.so.6",
        build_id=LIBC_BUILD_ID,
        sha256="a" * 64,
        size=4096,
        device=2049,
        inode=67890,
        mtime_ns=1,
        ctime_ns=2,
        executable_segments=(
            g4.ExecutableSegmentIdentity(0, 0, 0x1000, 0x1000, 0x1000),
            g4.ExecutableSegmentIdentity(0x2000, 0x2000, 0x1000, 0x1000, 0x1000),
        ),
    )


class StaticMapTests(unittest.TestCase):
    def test_raw_readelf_normalization_is_mechanical_and_hash_bound(self) -> None:
        segment_text, section_text = g4.normalize_readelf(
            READELF_PROGRAMS, READELF_SECTIONS, SECTION_HASH
        )
        parsed_segments = g4.parse_load_segments(segment_text)
        parsed_sections = g4.parse_executable_sections(section_text)
        self.assertEqual(parsed_segments[0].file_offset, 0x2000)
        self.assertEqual(parsed_segments[0].vaddr_start, 0x1000)
        self.assertEqual(parsed_segments[0].file_end, 0x2010)
        self.assertEqual(parsed_sections[0].name, ".text")
        self.assertEqual(parsed_sections[0].sha256, SECTION_HASH)

    def test_raw_readelf_normalization_rejects_locale_malformed_and_overlap(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "GNU readelf program-header schema"):
            g4.normalize_readelf(
                READELF_PROGRAMS.replace("Program Headers:", "En-tetes de programme:"),
                READELF_SECTIONS,
                SECTION_HASH,
            )
        with self.assertRaisesRegex(g4.MappingError, "binary SHA-256"):
            g4.normalize_readelf(READELF_PROGRAMS, READELF_SECTIONS, "bad")
        overlap = READELF_PROGRAMS + (
            "  LOAD           0x002008 0x0000000000003000 0x0000000000003000 "
            "0x000008 0x000008 R E 0x1000\n"
        )
        with self.assertRaisesRegex(g4.MappingError, "overlapping PT_LOAD file ranges"):
            g4.normalize_readelf(overlap, READELF_SECTIONS, SECTION_HASH)

    def test_full_instruction_map_is_mechanical_and_symbol_spelling_independent(self) -> None:
        rows = build_rows()
        self.assertEqual([row.instruction_vma for row in rows], [0x1000, 0x1001])
        self.assertEqual([row.dso_file_offset for row in rows], [0x2000, 0x2001])
        self.assertTrue(rows[0].raw_symbol.startswith("_ZN"))
        self.assertTrue(rows[0].emitted_family.startswith("ef:"))
        self.assertTrue(rows[0].source_family.startswith("sf:"))
        provenance = json.loads(rows[0].source_provenance_json)
        self.assertEqual(provenance["normalized_path"], "$SOURCE/src/foo.rs")
        self.assertEqual(provenance["innermost_item"], "cubrim::foo")
        self.assertEqual(provenance["source_domain"], "workspace")
        self.assertEqual(rows[0].resolution_status, "resolved")
        self.assertEqual(rows[0].frames[0].function, "cubrim::foo")
        rendered = g4.render_instruction_map(rows)
        self.assertEqual(g4.parse_instruction_map(rendered), rows)
        self.assertNotIn("bucket", rendered.lower())

    def test_conflicting_ordered_resolver_frames_are_rejected(self) -> None:
        changed = RESOLVER.replace("cubrim::foo\n/src/src/foo.rs:11", "cubrim::bar\n/src/src/bar.rs:11")
        with self.assertRaisesRegex(g4.MappingError, "conflicting ordered frame stacks"):
            g4.build_instruction_rows(
                segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010)),
                sections((".text", 0x1000, 0x1010, 0x2000)),
                OBJDUMP,
                RESOLVER,
                changed,
                PREFIXES,
                DSO,
            )

    def test_instruction_outside_executable_ranges_is_rejected(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "outside executable section"):
            g4.build_instruction_rows(
                segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010)),
                sections((".text", 0x2000, 0x2010, 0x3000)),
                OBJDUMP,
                RESOLVER,
                RESOLVER,
                PREFIXES,
                DSO,
            )

    def test_overlapping_executable_ranges_are_rejected(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "overlapping executable ranges"):
            g4.parse_executable_sections(
                sections((".text", 0x1000, 0x1010, 0x1000), (".plt", 0x1008, 0x1020, 0x2000))
            )

    def test_pt_load_conversion_is_bidirectionally_unique_when_vma_differs_from_file_offset(self) -> None:
        parsed = g4.parse_load_segments(
            segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010))
        )
        segment, offset = g4.vma_to_dso_offset(parsed, 0x1001, 1)
        self.assertEqual(segment.name, "LOAD0")
        self.assertEqual(offset, 0x2001)
        self.assertEqual(g4.dso_offset_to_vma(parsed, 0x2001, 1), 0x1001)
        self.assertNotEqual(offset, 0x1001)

    def test_duplicate_canonical_dso_offsets_from_segments_are_rejected(self) -> None:
        overlapping_file_offsets = segments(
            ("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010),
            ("LOAD1", 0x3000, 0x3010, 0x2000, 0x2010),
        )
        with self.assertRaisesRegex(g4.MappingError, "overlapping PT_LOAD file ranges"):
            g4.parse_load_segments(overlapping_file_offsets)

    def test_duplicate_instruction_address_is_rejected(self) -> None:
        duplicate = OBJDUMP + "    1001:\t90\t\tnop\n"
        parsed_sections = g4.parse_executable_sections(sections((".text", 0x1000, 0x1010, 0x1000)))
        with self.assertRaisesRegex(g4.MappingError, "duplicate instruction"):
            g4.parse_objdump(duplicate, parsed_sections)

    def test_no_source_frame_remains_explicit_binary_unresolved(self) -> None:
        unresolved = RESOLVER.replace("cubrim::foo\n/src/src/foo.rs:10", "??\n??:0")
        rows = g4.build_instruction_rows(
            segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010)),
            sections((".text", 0x1000, 0x1010, 0x2000)),
            OBJDUMP,
            unresolved,
            unresolved,
            PREFIXES,
            DSO,
        )
        self.assertEqual(rows[0].resolution_status, "binary_unresolved")
        self.assertEqual(rows[0].source_family, "special:binary_unresolved")

    def test_gnu_addr2line_unknown_location_is_explicit_binary_unresolved(self) -> None:
        unresolved = RESOLVER.replace("cubrim::foo\n/src/src/foo.rs:10", "??\n??:?")
        rows = g4.build_instruction_rows(
            segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010)),
            sections((".text", 0x1000, 0x1010, 0x2000)),
            OBJDUMP,
            unresolved,
            unresolved,
            PREFIXES,
            DSO,
        )
        self.assertEqual(rows[0].frames[0], g4.Frame(function="??", file="??", line=0))
        self.assertEqual(rows[0].resolution_status, "binary_unresolved")
        self.assertEqual(rows[0].source_family, "special:binary_unresolved")

    def test_gnu_addr2line_known_file_unknown_line_is_explicit_binary_unresolved(self) -> None:
        unresolved = RESOLVER.replace(
            "cubrim::foo\n/src/src/foo.rs:10",
            "deregister_tm_clones\ncrtstuff.c:?",
        )
        rows = g4.build_instruction_rows(
            segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010)),
            sections((".text", 0x1000, 0x1010, 0x2000)),
            OBJDUMP,
            unresolved,
            unresolved,
            PREFIXES,
            DSO,
        )
        self.assertEqual(
            rows[0].frames[0],
            g4.Frame(function="deregister_tm_clones", file="crtstuff.c", line=0),
        )
        self.assertEqual(rows[0].resolution_status, "binary_unresolved")
        self.assertEqual(rows[0].source_family, "special:binary_unresolved")

    def test_resolver_rejects_nearby_malformed_unknown_locations(self) -> None:
        for malformed in (":?", "?:?", "??:unknown", "??:? extra", "crtstuff.c:??", "??"):
            with self.subTest(malformed=malformed):
                resolver = RESOLVER.replace("/src/src/foo.rs:10", malformed)
                with self.assertRaisesRegex(g4.MappingError, "malformed resolver location"):
                    g4.parse_resolver(resolver)

    def test_source_family_reverse_index_rejects_collision(self) -> None:
        rows = build_rows()
        provenance = json.loads(rows[1].source_provenance_json)
        provenance["innermost_item"] = "cubrim::different_closure"
        collided = dataclasses.replace(
            rows[1], source_family=rows[0].source_family,
            source_provenance_json=json.dumps(provenance, sort_keys=True, separators=(",", ":")),
        )
        with self.assertRaisesRegex(g4.MappingError, "source-family key collision"):
            g4.build_family_reverse_index([rows[0], collided])

    def test_prefix_table_rejects_traversal_and_unmapped_absolute_source(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "unsafe prefix replacement"):
            g4.parse_prefix_table(
                "source_domain\tpackage_identity\tprefix\treplacement\n"
                "workspace\trepo:cubrim@x\t/src\t../escape\n"
            )
        unmapped = RESOLVER.replace("/src/src/foo.rs", "/outside/foo.rs")
        with self.assertRaisesRegex(g4.MappingError, "no frozen prefix"):
            g4.build_instruction_rows(
                segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010)),
                sections((".text", 0x1000, 0x1010, 0x2000)),
                OBJDUMP,
                unmapped,
                unmapped,
                PREFIXES,
                DSO,
            )

    def test_rustc_and_ring_dotdot_sources_normalize_without_changing_raw_frames(self) -> None:
        rustc_raw = (
            "/rustc/31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd/"
            "library/core/src/../../alloc/src/raw_vec/mod.rs"
        )
        ring_raw = (
            "/root/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/"
            "ring-0.17.14/crypto/fipsmodule/../../crypto/limbs/limbs.c"
        )
        rules = g4.parse_prefix_table(
            PREFIXES
            + "cargo_registry\tcrate-registry:crates.io\t/root/.cargo/registry/src\t$CARGO_REGISTRY\n"
        )
        cases = (
            (
                rustc_raw,
                "$RUST/31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd/library/alloc/src/raw_vec/mod.rs",
            ),
            (
                ring_raw,
                "$CARGO_REGISTRY/index.crates.io-1949cf8c6b5b557f/"
                "ring-0.17.14/crypto/limbs/limbs.c",
            ),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                frames = (g4.Frame("observed::frame", raw, 42),)
                _, encoded, status = g4.provenance_for(frames, "raw_symbol", rules)
                provenance = json.loads(encoded)
                self.assertEqual(status, "resolved")
                self.assertEqual(provenance["normalized_path"], expected)
                self.assertEqual(
                    provenance["frame_stack_sha256"],
                    hashlib.sha256(g4.frame_json(frames).encode()).hexdigest(),
                )
                self.assertEqual(frames[0].file, raw)

    def test_source_normalization_rejects_root_prefix_escape_and_controls(self) -> None:
        rules = g4.parse_prefix_table(PREFIXES)
        for unsafe in (
            "/src/../../etc/passwd",
            "/src/../etc/passwd",
            "/src/source/\x00hidden.rs",
        ):
            with self.subTest(unsafe=repr(unsafe)):
                with self.assertRaisesRegex(
                    g4.MappingError,
                    "escapes root|escapes frozen prefix|no frozen prefix|unsafe resolver source path",
                ):
                    g4.normalize_source(unsafe, rules)

    def test_relative_unknown_numeric_location_remains_binary_unresolved(self) -> None:
        frames = g4.parse_resolver("0x1000\n??\n??:0\n")[0x1000]
        family, encoded, status = g4.provenance_for(
            frames,
            "raw_symbol",
            g4.parse_prefix_table(PREFIXES),
        )
        self.assertEqual(frames, (g4.Frame("??", "??", 0),))
        self.assertEqual((family, encoded, status), ("special:binary_unresolved", "{}", "binary_unresolved"))


class GzipTests(unittest.TestCase):
    def test_required_g5_map_schemas_are_exact(self) -> None:
        source_tree = ast.parse(Path(g4.__file__).read_text(encoding="utf-8"))
        emitted_schemas = {
            value.value
            for node in ast.walk(source_tree)
            if isinstance(node, ast.Dict)
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant)
            and key.value == "schema"
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        }
        self.assertTrue({
            "cubr-new24-g5-normalized-elf-v1",
            "cubr-new24-g5-static-map-summary-v3",
            "cubr-new24-g5-map-parts-v1",
            "cubr-new24-g5-map-admission-seal-v1",
        }.issubset(emitted_schemas), emitted_schemas)

    def test_every_emitted_schema_is_g5_namespaced_without_fresh_output_residue(self) -> None:
        source_tree = ast.parse(Path(g4.__file__).read_text(encoding="utf-8"))
        emitted_schemas = [
            value.value
            for node in ast.walk(source_tree)
            if isinstance(node, ast.Dict)
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant)
            and key.value == "schema"
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ]
        self.assertTrue(emitted_schemas)
        self.assertTrue(
            all(schema.startswith("cubr-new24-g5-") for schema in emitted_schemas),
            emitted_schemas,
        )

        _, manifest = g4.split_instruction_map(build_rows(), max_rows=1, part_prefix="g5-map")
        record = g4.reduce_record(
            build_rows(),
            g4.parse_load_segments(segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010))),
            perf_text("100 0x400000 (/opt/cubrim+0x2000)"),
            {DSO: BUILD_ID},
            identity(),
            page_size=PAGE_SIZE,
            simultaneous_records=6,
        )
        fresh_output = json.dumps(
            [manifest, record, g4.summarize_file("dickens/max", record, record)],
            sort_keys=True,
        )
        self.assertNotIn("cubr-new24-g4-", fresh_output)

    def test_gzip_is_deterministic_and_round_trips(self) -> None:
        payload = g4.render_instruction_map(build_rows()).encode()
        first = g4.deterministic_gzip(payload)
        second = g4.deterministic_gzip(payload)
        self.assertEqual(first, second)
        self.assertEqual(first[4:8], b"\0\0\0\0")
        self.assertEqual(gzip.decompress(first), payload)
        evidence = g4.gzip_evidence(payload, first)
        self.assertEqual(evidence["uncompressed_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(evidence["compressed_sha256"], hashlib.sha256(first).hexdigest())

    def test_split_manifest_reassembles_exact_canonical_stream(self) -> None:
        rows = build_rows()
        parts, manifest = g4.split_instruction_map(rows, max_rows=1, part_prefix="map")
        self.assertEqual(len(parts), 2)
        self.assertEqual([item["part_index"] for item in manifest["parts"]], [0, 1])
        self.assertEqual([item["path"] for item in manifest["parts"]], [
            "map.part-00000.tsv.gz", "map.part-00001.tsv.gz"
        ])
        self.assertEqual(
            g4.verify_map_parts(parts, manifest),
            g4.render_instruction_map(rows).encode(),
        )

    def test_split_manifest_rejects_extra_member_part_and_decompression_bomb(self) -> None:
        parts, manifest = g4.split_instruction_map(build_rows(), max_rows=1)
        with self.assertRaisesRegex(g4.MappingError, "extra gzip member|trailing"):
            g4.verify_map_parts([parts[0] + g4.deterministic_gzip(b"extra"), parts[1]], manifest)
        with self.assertRaisesRegex(g4.MappingError, "part count"):
            g4.verify_map_parts(parts + [parts[0]], manifest)
        with self.assertRaisesRegex(g4.MappingError, "decompression limit"):
            g4.decompress_single_gzip(parts[0], max_bytes=4)

        ceiling = 512 * 1024 * 1024
        self.assertEqual(g4.MAX_MAP_PART_UNCOMPRESSED_BYTES, ceiling)
        for label, value in (
            ("missing", None), ("string", "1"), ("boolean", True),
            ("negative", -1), ("over-ceiling", ceiling + 1),
        ):
            with self.subTest(uncompressed_bytes=label):
                mutated = copy.deepcopy(manifest)
                if value is None:
                    del mutated["parts"][0]["uncompressed_bytes"]
                else:
                    mutated["parts"][0]["uncompressed_bytes"] = value
                with mock.patch.object(g4, "decompress_single_gzip") as decoder:
                    with self.assertRaisesRegex(g4.MappingError, "invalid map part uncompressed byte count"):
                        g4.verify_map_parts(parts, mutated)
                    decoder.assert_not_called()

        real_decoder = g4.decompress_single_gzip
        observed_limits: list[int] = []

        def fixed_ceiling_decoder(compressed: bytes, *, max_bytes: int = ceiling) -> bytes:
            observed_limits.append(max_bytes)
            return real_decoder(compressed, max_bytes=max_bytes)

        with mock.patch.object(g4, "decompress_single_gzip", side_effect=fixed_ceiling_decoder):
            self.assertEqual(
                g4.verify_map_parts(parts, manifest),
                g4.render_instruction_map(build_rows()).encode(),
            )
        self.assertEqual(observed_limits, [ceiling] * len(parts))
        with mock.patch.object(
            g4, "decompress_single_gzip",
            side_effect=g4.MappingError("decompression limit exceeded"),
        ):
            with self.assertRaisesRegex(g4.MappingError, "decompression limit"):
                g4.verify_map_parts(parts, manifest)


class AdmissionSealTests(unittest.TestCase):
    def seal(self, **overrides: object) -> dict:
        arguments = {
            "binary_build_id": BUILD_ID,
            "binary_sha256": "1" * 64,
            "instrument_resulting_main": "2" * 40,
            "map_artifacts": [
                {"path": "map/z.tsv.gz", "bytes": 2, "sha256": "3" * 64},
                {"path": "map/a.json", "bytes": 1, "sha256": "4" * 64},
            ],
            "mapper_sha256": "5" * 64,
            "mapper_test_sha256": "6" * 64,
            "mapping_schema_sha256": "7" * 64,
            "reuse_decision": "REJECTED_IDENTITY_MISMATCH",
            "source_tree": "8" * 40,
            "toolchain": {"rustc": "rustc 1.96.1", "cargo": "cargo 1.96.1"},
        }
        arguments.update(overrides)
        return g4.build_g5_admission_seal(**arguments)

    def complete_identity(self) -> dict:
        return self.seal(reuse_decision="REUSED_IDENTITY_MATCH")

    def test_complete_identical_identity_is_reusable(self) -> None:
        identity = self.complete_identity()
        self.assertEqual(
            g4.g5_reuse_decision(identity, copy.deepcopy(identity)),
            "REUSED_IDENTITY_MATCH",
        )

    def test_missing_identity_axes_are_rejected(self) -> None:
        identity = self.complete_identity()
        axis_field_variants = {
            "mapper_sha256": (("mapper_sha256",),),
            "mapper_test_sha256": (("mapper_test_sha256",),),
            "mapping_schema_sha256": (("mapping_schema_sha256",),),
            "source_tree": (("source_tree",),),
            "binary_sha256_build_id": (
                ("binary_sha256",),
                ("binary_build_id",),
                ("binary_sha256", "binary_build_id"),
            ),
            "toolchain": (("toolchain",),),
            "page_size": (("page_size",),),
            "map_artifacts": (("map_artifacts",),),
        }
        self.assertEqual(len(axis_field_variants), 8)
        for axis, variants in axis_field_variants.items():
            for fields in variants:
                with self.subTest(identity_axis=axis, missing_fields=fields):
                    incomplete = copy.deepcopy(identity)
                    for field in fields:
                        incomplete.pop(field)
                    self.assertEqual(
                        g4.g5_reuse_decision(incomplete, copy.deepcopy(incomplete)),
                        "REJECTED_IDENTITY_MISMATCH",
                    )
                    self.assertEqual(
                        g4.g5_reuse_decision(identity, incomplete),
                        "REJECTED_IDENTITY_MISMATCH",
                    )
                    self.assertEqual(
                        g4.g5_reuse_decision(incomplete, identity),
                        "REJECTED_IDENTITY_MISMATCH",
                    )

    def test_partial_identity_is_rejected(self) -> None:
        identity = self.complete_identity()
        partials = [
            {},
            {"mapper_sha256": identity["mapper_sha256"]},
            {
                "mapper_sha256": identity["mapper_sha256"],
                "mapper_test_sha256": identity["mapper_test_sha256"],
                "mapping_schema_sha256": identity["mapping_schema_sha256"],
            },
        ]
        for partial in partials:
            with self.subTest(fields=sorted(partial)):
                self.assertEqual(
                    g4.g5_reuse_decision(partial, copy.deepcopy(partial)),
                    "REJECTED_IDENTITY_MISMATCH",
                )

    def test_invalid_identity_shapes_and_types_are_rejected(self) -> None:
        identity = self.complete_identity()
        invalid_identities: dict[str, object] = {}

        def invalid(label: str, **changes: object) -> None:
            candidate = copy.deepcopy(identity)
            candidate.update(changes)
            invalid_identities[label] = candidate

        invalid("mapper_sha256_type", mapper_sha256=bytes(32))
        invalid("mapper_sha256_shape", mapper_sha256="A" * 64)
        invalid("mapper_test_sha256_shape", mapper_test_sha256="6" * 63)
        invalid("mapping_schema_sha256_shape", mapping_schema_sha256="not-a-sha")
        invalid("source_tree_shape", source_tree="8" * 39)
        invalid("binary_sha256_shape", binary_sha256="1" * 63)
        invalid("binary_build_id_shape", binary_build_id="not-hex")
        invalid("page_size_bool", page_size=True)
        invalid("page_size_value", page_size=8192)
        invalid("toolchain_type", toolchain=[])
        invalid("toolchain_empty", toolchain={})
        invalid("toolchain_nested", toolchain={"rustc": {"version": "1.96.1"}})
        invalid("map_artifacts_type", map_artifacts=())
        invalid("map_artifacts_empty", map_artifacts=[])
        invalid("map_artifact_missing_field", map_artifacts=[{
            "path": "map/a.json", "sha256": "4" * 64,
        }])
        invalid("map_artifact_extra_field", map_artifacts=[{
            "path": "map/a.json", "bytes": 1, "sha256": "4" * 64,
            "extra": "not-sealed",
        }])
        invalid("map_artifact_unsafe_path", map_artifacts=[{
            "path": "../map/a.json", "bytes": 1, "sha256": "4" * 64,
        }])
        invalid("map_artifact_bytes_type", map_artifacts=[{
            "path": "map/a.json", "bytes": True, "sha256": "4" * 64,
        }])
        invalid("map_artifact_sha256_shape", map_artifacts=[{
            "path": "map/a.json", "bytes": 1, "sha256": "invalid",
        }])
        invalid("map_artifact_duplicate_path", map_artifacts=[
            {"path": "map/a.json", "bytes": 1, "sha256": "4" * 64},
            {"path": "map/a.json", "bytes": 2, "sha256": "3" * 64},
        ])
        invalid("map_artifact_unsorted", map_artifacts=[
            {"path": "map/z.tsv.gz", "bytes": 2, "sha256": "3" * 64},
            {"path": "map/a.json", "bytes": 1, "sha256": "4" * 64},
        ])
        invalid_identities["outer_list"] = []
        invalid_identities["outer_none"] = None
        for label, malformed in invalid_identities.items():
            with self.subTest(invalid_identity=label):
                self.assertEqual(
                    g4.g5_reuse_decision(malformed, copy.deepcopy(malformed)),  # type: ignore[arg-type]
                    "REJECTED_IDENTITY_MISMATCH",
                )
                self.assertEqual(
                    g4.g5_reuse_decision(identity, malformed),  # type: ignore[arg-type]
                    "REJECTED_IDENTITY_MISMATCH",
                )

    def test_g4_identity_reuse_is_rejected(self) -> None:
        g4_identity = self.seal(
            mapper_sha256="36226ff6caf35983a97fa472b1433e37f18a6ac4b565d1ae016e27cd957ae5e1",
            mapper_test_sha256="97af2daacca00b20d9eb56dee34d56f9a3a9c22ffcdba820bfce171e7a371314",
            mapping_schema_sha256="1c8f5be539eaaa94f3a64d071e859ee5eccf8f4314908e143246f47bd8760e12",
            reuse_decision="REUSED_IDENTITY_MATCH",
        )
        g4_identity["schema"] = "cubr-new24-g4-map-admission-seal-v1"
        mutations = {
            "mapper_sha256": [{"mapper_sha256": "5" * 64}],
            "mapper_test_sha256": [{"mapper_test_sha256": "6" * 64}],
            "mapping_schema_sha256": [{"mapping_schema_sha256": "7" * 64}],
            "source_tree": [{"source_tree": "c" * 40}],
            "binary_sha256_build_id": [
                {"binary_sha256": "d" * 64},
                {"binary_build_id": "e" * 40},
            ],
            "toolchain": [{
                "toolchain": {"cargo": "cargo changed", "rustc": "rustc 1.96.1"}
            }],
            "page_size": [{"page_size": 8192}],
            "map_artifacts": [{"map_artifacts": [
                {"path": "map/a.json", "bytes": 1, "sha256": "f" * 64},
                {"path": "map/z.tsv.gz", "bytes": 2, "sha256": "3" * 64},
            ]}],
        }
        self.assertEqual(len(mutations), 8)
        for axis, variants in mutations.items():
            for changes in variants:
                with self.subTest(identity_axis=axis, changes=changes):
                    candidate = copy.deepcopy(g4_identity)
                    candidate.update(changes)
                    self.assertEqual(
                        g4.g5_reuse_decision(g4_identity, candidate),
                        "REJECTED_IDENTITY_MISMATCH",
                    )

        fresh = self.seal()
        self.assertEqual(fresh["reuse_decision"], "REJECTED_IDENTITY_MISMATCH")
        self.assertEqual(fresh["performance_sample"], "NO")
        self.assertEqual(fresh["schema"], "cubr-new24-g5-map-admission-seal-v1")

    def test_seal_is_compact_deterministic_and_sorts_identity_maps(self) -> None:
        first = self.seal()
        second = self.seal(
            map_artifacts=list(reversed(first["map_artifacts"])),
            toolchain={"cargo": "cargo 1.96.1", "rustc": "rustc 1.96.1"},
        )
        self.assertEqual(first, second)
        self.assertEqual(first["page_size"], 4096)
        self.assertEqual(
            g4.json_bytes(first),
            (json.dumps(first, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )

    def test_seal_admission_uses_single_output_join(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output_root = Path(td) / "partial"
            map_root = output_root / "map"
            preflight_root = output_root / "preflight"
            map_root.mkdir(parents=True)
            preflight_root.mkdir()

            part_blobs, manifest = g4.split_instruction_map(
                build_rows(), max_rows=10, part_prefix="g5-map"
            )
            part_name = manifest["parts"][0]["path"]
            (map_root / part_name).write_bytes(part_blobs[0])
            (map_root / "map-parts-manifest.json").write_bytes(g4.json_bytes(manifest))
            summary_payload = g4.json_bytes({
                "schema": "cubr-new24-g5-static-map-summary-v3",
                "mapping_schema_sha256": "7" * 64,
            })
            summary_blob = g4.deterministic_gzip(summary_payload)
            (map_root / "map-summary.json.gz").write_bytes(summary_blob)
            (map_root / "raw-stream-evidence.tsv").write_text(
                "source\tuncompressed_bytes\tuncompressed_sha256\tcompressed\tcompressed_bytes\tcompressed_sha256\n"
                f"map-summary.json\t{len(summary_payload)}\t{hashlib.sha256(summary_payload).hexdigest()}\t"
                f"map-summary.json.gz\t{len(summary_blob)}\t{hashlib.sha256(summary_blob).hexdigest()}\n",
                encoding="utf-8",
            )
            (preflight_root / "map-toolchain.json").write_bytes(g4.json_bytes({
                "cargo": "cargo 1.96.1",
                "rustc": "rustc 1.96.1",
            }))

            parser = g4.make_parser()
            with mock.patch.object(
                g4, "build_g5_admission_seal", wraps=g4.build_g5_admission_seal
            ) as constructor:
                g4.run_command(parser.parse_args([
                    "seal-admission", "--input-root", str(output_root),
                    "--output-root", str(map_root), "--binary-build-id", BUILD_ID,
                    "--binary-sha256", "1" * 64, "--instrument-resulting-main", "2" * 40,
                    "--mapper-sha256", "5" * 64, "--mapper-test-sha256", "6" * 64,
                    "--mapping-schema-sha256", "7" * 64,
                    "--reuse-decision", "REJECTED_IDENTITY_MISMATCH",
                    "--source-tree", "8" * 40,
                    "--toolchain-json", "preflight/map-toolchain.json",
                    "--map-manifest", "map/map-parts-manifest.json",
                    "--map-summary", "map/map-summary.json.gz",
                    "--raw-stream-evidence", "map/raw-stream-evidence.tsv",
                    "--seal-out", "map-admission-seal.json",
                ]))
            self.assertEqual(constructor.call_count, 1)
            seal_path = output_root / "map" / "map-admission-seal.json"
            nested_path = output_root / "map" / "map" / "map-admission-seal.json"
            self.assertTrue(seal_path.is_file())
            self.assertFalse(nested_path.exists())
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            self.assertEqual(seal["reuse_decision"], "REJECTED_IDENTITY_MISMATCH")
            self.assertEqual(seal["performance_sample"], "NO")
            self.assertEqual(seal["schema"], "cubr-new24-g5-map-admission-seal-v1")
            self.assertEqual(seal["toolchain"], {
                "cargo": "cargo 1.96.1", "rustc": "rustc 1.96.1"
            })
            self.assertEqual(
                {row["path"] for row in seal["map_artifacts"]},
                {
                    "map/g5-map.part-00000.tsv.gz",
                    "map/map-parts-manifest.json",
                    "map/map-summary.json.gz",
                    "map/raw-stream-evidence.tsv",
                },
            )
            self.assertEqual(
                seal_path.read_bytes(),
                (json.dumps(seal, sort_keys=True, separators=(",", ":")) + "\n").encode(),
            )


class RuntimeJoinTests(unittest.TestCase):
    def reduce(self, text: str, rows: list[g4.InstructionRow] | None = None) -> dict:
        return g4.reduce_record(
            rows or build_rows(),
            g4.parse_load_segments(segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010))),
            text,
            {DSO: BUILD_ID, "/lib/libc.so.6": LIBC_BUILD_ID},
            identity(),
            page_size=PAGE_SIZE,
            simultaneous_records=6,
            other_dso_snapshots={"/lib/libc.so.6": libc_snapshot()}
            if "/lib/libc.so.6" in text else {},
        )

    def test_runtime_join_uses_only_mmap_formula_dsoff_and_instruction_address(self) -> None:
        libc_mmap = (
            f"PERF_RECORD_MMAP2 10/10: [0x700000(0x1000) @ 0x2000 <{LIBC_BUILD_ID}>]: "
            "r-xp /lib/libc.so.6\n"
        )
        result = self.reduce(perf_text(
            "100 0x400000 (/opt/cubrim+0x2000)",
            "50 0x400001 (/opt/cubrim+0x2001)",
            "20 0xffffffff81000000 ([kernel.kallsyms]+0x10)",
            "30 0x700000 (/lib/libc.so.6+0x2000)", other_mmaps=libc_mmap,
        ))
        self.assertEqual(result["raw_sample_count"], 4)
        self.assertEqual(result["raw_total_period"], 200)
        self.assertEqual(result["binary_sample_count"], 2)
        self.assertEqual(result["binary_sum_period"], 150)
        self.assertNotIn("binary_effective_sample_size", result)
        self.assertAlmostEqual(result["binary_zero_hit_upper_bound"], 1 - (0.05 / 6) ** 0.5)
        self.assertIn(build_rows()[0].source_family, result["families"])
        self.assertEqual(result["families"]["special:kernel"]["sum_period"], 20)
        self.assertEqual(result["families"]["special:other_dso"]["sum_period"], 30)
        self.assertFalse(result["symbol_consulted"])
        self.assertIn(build_rows()[0].emitted_family, result["emitted_families"])

    def test_exact_binomial_bound_uses_sample_rows_and_frozen_threshold(self) -> None:
        self.assertGreater(g4.zero_hit_upper_bound(4785), 0.001)
        self.assertLessEqual(g4.zero_hit_upper_bound(4786), 0.001)
        self.assertLessEqual(g4.zero_hit_upper_bound(4787), 0.001)
        self.assertIsNone(g4.zero_hit_upper_bound(0))

    def test_bad_dsoff_is_rejected(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "dsoff mismatch"):
            self.reduce(perf_text("100 0x400000 (/opt/cubrim+0x2001)"))

    def test_exact_binary_mmap_must_equal_frozen_executable_segment(self) -> None:
        for mutated, reason in (
            ("@ 0x0", "file range"),
            ("(0x3000)", "file range"),
            ("(0x2000)", "file range"),
            ("rwxp", "protection"),
        ):
            with self.subTest(mutated=mutated):
                text = perf_text("100 0x400000 (/opt/cubrim+0x2000)")
                if mutated.startswith("@"):
                    text = text.replace("@ 0x2000", mutated)
                elif mutated.startswith("("):
                    text = text.replace("(0x1000)", mutated)
                else:
                    text = text.replace("r-xp", mutated)
                with self.assertRaisesRegex(g4.MappingError, reason):
                    self.reduce(text)

    def test_sampled_unresolved_or_ambiguous_binary_row_is_hard_void(self) -> None:
        for status in ("binary_unresolved", "ambiguous_inline_owner"):
            with self.subTest(status=status):
                rows = build_rows()
                if status == "binary_unresolved":
                    rows[0] = dataclasses.replace(
                        rows[0], resolution_status=status,
                        source_family="special:binary_unresolved", source_provenance_json="{}",
                    )
                else:
                    rows[0] = dataclasses.replace(rows[0], resolution_status=status)
                with self.assertRaisesRegex(g4.MappingError, "sampled unresolved or ambiguous"):
                    self.reduce(perf_text("100 0x400000 (/opt/cubrim+0x2000)"), rows)

    def test_unknown_or_malformed_dso_identity_is_hard_void(self) -> None:
        for dso in ("unknown", "(unknown)", "[unknown]", "[madeup]", "relative.so", "/lib/../evil.so"):
            with self.subTest(dso=dso):
                with self.assertRaisesRegex(g4.MappingError, "unknown or malformed DSO identity"):
                    self.reduce(perf_text(f"100 0x700000 ({dso}+0x0)"))

    def test_other_dso_snapshot_manifest_has_exact_sampled_cardinality(self) -> None:
        text = perf_text("100 0x700020 (/lib/libc.so.6+0x20)")
        args = (
            build_rows(),
            g4.parse_load_segments(segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010))),
            text,
            {DSO: BUILD_ID, "/lib/libc.so.6": LIBC_BUILD_ID},
            identity(),
        )
        with self.assertRaisesRegex(g4.MappingError, "snapshot cardinality"):
            g4.reduce_record(*args, other_dso_snapshots={})
        extra = dataclasses.replace(libc_snapshot(), path="/opt/extra.so")
        with self.assertRaisesRegex(g4.MappingError, "snapshot cardinality"):
            g4.reduce_record(
                *args,
                other_dso_snapshots={
                    "/lib/libc.so.6": libc_snapshot(),
                    "/opt/extra.so": extra,
                },
            )

    def test_other_dso_snapshot_must_match_buildid_list_and_mmap(self) -> None:
        text = perf_text("100 0x700020 (/lib/libc.so.6+0x20)")
        bad = dataclasses.replace(libc_snapshot(), build_id="f" * 40)
        with self.assertRaisesRegex(g4.MappingError, "authenticated build ID"):
            g4.reduce_record(
                build_rows(),
                g4.parse_load_segments(segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010))),
                text,
                {DSO: BUILD_ID, "/lib/libc.so.6": LIBC_BUILD_ID},
                identity(),
                other_dso_snapshots={"/lib/libc.so.6": bad},
            )

    def test_frozen_kernel_and_preregistered_pseudo_dsos_are_accepted(self) -> None:
        result = self.reduce(perf_text(
            "10 0xffffffff81000000 ([kernel.kallsyms]+0x10)",
            "20 0x7fff0000 ([vdso]+0x10)",
        ))
        self.assertEqual(result["families"]["special:kernel"]["sum_period"], 10)
        self.assertEqual(result["families"]["special:other_dso"]["sum_period"], 20)

    def test_vma_spelling_is_not_accepted_as_canonical_dso_offset(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "dsoff mismatch"):
            self.reduce(perf_text("100 0x400000 (/opt/cubrim+0x1000)"))

    def test_unknown_exact_binary_instruction_is_rejected_without_rounding(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "unknown exact-binary instruction"):
            self.reduce(perf_text("100 0x400002 (/opt/cubrim+0x2002)"))

    def test_overlapping_applicable_mmaps_are_rejected(self) -> None:
        overlap = (
            f"PERF_RECORD_MMAP2 10/10: [0x400000(0x1000) @ 0x2000 <{BUILD_ID}>]: "
            "r-xp /opt/cubrim\n"
        )
        with self.assertRaisesRegex(g4.MappingError, "exactly one executable MMAP2"):
            self.reduce(perf_text("100 0x400000 (/opt/cubrim+0x2000)", second_mmap=overlap))

    def test_multiple_nonoverlapping_exact_binary_mmaps_are_also_rejected(self) -> None:
        second = (
            f"PERF_RECORD_MMAP2 10/10: [0x500000(0x1000) @ 0x3000 <{BUILD_ID}>]: "
            "r-xp /opt/cubrim\n"
        )
        with self.assertRaisesRegex(g4.MappingError, "exactly one executable MMAP2"):
            self.reduce(perf_text("100 0x400000 (/opt/cubrim+0x2000)", second_mmap=second))

    def test_lost_record_is_rejected(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "lost record"):
            self.reduce(perf_text("PERF_RECORD_LOST lost=2"))

    def test_build_id_or_mmap_identity_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(g4.MappingError, "build ID mismatch"):
            g4.reduce_record(
                build_rows(),
                g4.parse_load_segments(segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010))),
                perf_text("10 0x400000 (/opt/cubrim+0x2000)"), {DSO: "f" * 40}, identity(),
            )
        device_union = (
            "PERF_RECORD_MMAP2 10/10: [0x400000(0x1000) @ 0x2000 "
            "08:01 12345 0]: r-xp /opt/cubrim\n"
            "10 0x400000 (/opt/cubrim+0x2000)\n"
        )
        with self.assertRaisesRegex(g4.MappingError, "build-ID union"):
            self.reduce(device_union)
        wrong_mmap_build_id = perf_text(
            "10 0x400000 (/opt/cubrim+0x2000)"
        ).replace(BUILD_ID, "f" * 40)
        with self.assertRaisesRegex(g4.MappingError, "MMAP2 build ID mismatch"):
            self.reduce(wrong_mmap_build_id)

    def test_period_sample_and_square_conservation_mutation_is_detected(self) -> None:
        result = self.reduce(perf_text("10 0x400000 (/opt/cubrim+0x2000)"))
        mutated = json.loads(json.dumps(result["families"]))
        mutated[build_rows()[0].source_family]["sum_period_squared"] += 1
        with self.assertRaisesRegex(g4.MappingError, "squared-period conservation"):
            g4.validate_conservation(
                mutated,
                result["raw_sample_count"],
                result["raw_total_period"],
                result["raw_total_period_squared"],
            )

    def test_per_file_material_families_use_both_records_without_cross_file_reduction(self) -> None:
        first = self.reduce(perf_text(
            "90 0x400000 (/opt/cubrim+0x2000)", "10 0x700020 (/lib/libc.so.6+0x20)"
        ))
        second = self.reduce(perf_text(
            "89 0x400000 (/opt/cubrim+0x2000)", "11 0x700020 (/lib/libc.so.6+0x20)"
        ))
        summary = g4.summarize_file("dickens/max", first, second)
        family = summary["material_families"][build_rows()[0].source_family]
        self.assertEqual(family["record_shares_percent"], [90.0, 89.0])
        self.assertEqual(family["delta_percentage_points"], 1.0)
        self.assertTrue(family["repeatable"])
        self.assertAlmostEqual(family["perfect_family_amdahl_ceiling"], 1 / (1 - 0.895))
        self.assertFalse(summary["cross_file_reduction_performed"])

    def test_family_is_material_when_threshold_is_met_in_either_record(self) -> None:
        first = self.reduce(perf_text(
            "9 0x400000 (/opt/cubrim+0x2000)", "91 0x700020 (/lib/libc.so.6+0x20)"
        ))
        second = self.reduce(perf_text(
            "4 0x400000 (/opt/cubrim+0x2000)", "96 0x700020 (/lib/libc.so.6+0x20)"
        ))
        family = g4.summarize_file("xml/max", first, second)["material_families"][
            build_rows()[0].source_family
        ]
        self.assertEqual(family["record_shares_percent"], [9.0, 4.0])
        self.assertFalse(family["repeatable"])

    def test_special_buckets_are_exhaustive_but_never_p5_source_candidates(self) -> None:
        first = self.reduce(perf_text(
            "4 0x400000 (/opt/cubrim+0x2000)", "96 0x700020 (/lib/libc.so.6+0x20)"
        ))
        second = self.reduce(perf_text(
            "4 0x400000 (/opt/cubrim+0x2000)", "96 0x700020 (/lib/libc.so.6+0x20)"
        ))
        summary = g4.summarize_file("xml/max", first, second)
        special = summary["source_families"]["special:other_dso"]
        self.assertEqual(special["record_shares_percent"], [96.0, 96.0])
        self.assertFalse(special["p5_eligible"])
        self.assertFalse(special["material"])
        self.assertFalse(special["repeatable"])
        self.assertIsNone(special["perfect_family_amdahl_ceiling"])
        self.assertNotIn("special:other_dso", summary["material_source_families"])
        self.assertTrue(all(key.startswith("sf:") for key in summary["material_families"]))


class FilesystemAndCliTests(unittest.TestCase):
    def test_live_other_dso_snapshot_is_same_fd_buildid_and_pt_load_bound(self) -> None:
        source = Path("/usr/bin/true").resolve(strict=True)
        expected_build_id = g4.read_elf_build_id(source)
        snapshot = g4.authenticate_other_dso_snapshot(source, expected_build_id)
        self.assertEqual(str(source), snapshot.path)
        self.assertEqual(expected_build_id, snapshot.build_id)
        self.assertTrue(snapshot.executable_segments)
        self.assertEqual(
            snapshot,
            g4.verify_other_dso_snapshot(source, snapshot),
        )

    def test_other_dso_snapshot_rejects_missing_symlink_and_nonregular(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing = root / "missing.so"
            with self.assertRaisesRegex(g4.MappingError, "missing other DSO"):
                g4.authenticate_other_dso_snapshot(missing, "a" * 40)
            target = Path("/usr/bin/true").resolve(strict=True)
            linked = root / "linked.so"
            linked.symlink_to(target)
            with self.assertRaisesRegex(g4.MappingError, "symlink"):
                g4.authenticate_other_dso_snapshot(linked, g4.read_elf_build_id(target))
            with self.assertRaisesRegex(g4.MappingError, "regular"):
                g4.authenticate_other_dso_snapshot(root, "a" * 40)

    def test_other_dso_snapshot_rejects_buildid_mismatch_and_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / "dso.so"
            shutil.copy2(Path("/usr/bin/true").resolve(strict=True), binary)
            expected_build_id = g4.read_elf_build_id(binary)
            with self.assertRaisesRegex(g4.MappingError, "build ID mismatch"):
                g4.authenticate_other_dso_snapshot(binary, "f" * len(expected_build_id))
            snapshot = g4.authenticate_other_dso_snapshot(binary, expected_build_id)
            with binary.open("ab") as handle:
                handle.write(b"mutation")
                handle.flush()
                os.fsync(handle.fileno())
            with self.assertRaisesRegex(g4.MappingError, "snapshot mismatch"):
                g4.verify_other_dso_snapshot(binary, snapshot)

    def test_other_dso_snapshot_detects_same_fd_race(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / "dso.so"
            shutil.copy2(Path("/usr/bin/true").resolve(strict=True), binary)
            expected_build_id = g4.read_elf_build_id(binary)
            real_run = g4.subprocess.run

            def mutate_after_readelf(*args, **kwargs):
                result = real_run(*args, **kwargs)
                with binary.open("ab") as handle:
                    handle.write(b"raced")
                    handle.flush()
                    os.fsync(handle.fileno())
                return result

            with mock.patch.object(g4.subprocess, "run", side_effect=mutate_after_readelf):
                with self.assertRaisesRegex(g4.MappingError, "changed during authentication"):
                    g4.authenticate_other_dso_snapshot(binary, expected_build_id)

    def test_build_and_reduce_cli_round_trip_multipart_map(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            inputs, built, reduced = base / "inputs", base / "built", base / "reduced"
            inputs.mkdir()
            built.mkdir()
            reduced.mkdir()
            fixtures = {
                "segments.tsv": segments(("LOAD0", 0x1000, 0x1010, 0x2000, 0x2010)),
                "sections.tsv": sections((".text", 0x1000, 0x1010, 0x2000)),
                "objdump.txt": OBJDUMP,
                "resolver-a.txt": RESOLVER,
                "resolver-b.txt": RESOLVER,
                "prefixes.tsv": PREFIXES,
            }
            for name, value in fixtures.items():
                (inputs / name).write_text(value, encoding="utf-8")
            parser = g4.make_parser()
            g4.run_command(parser.parse_args([
                "build-map", "--input-root", str(inputs), "--output-root", str(built),
                "--segments", "segments.tsv", "--sections", "sections.tsv",
                "--objdump", "objdump.txt", "--resolver-a", "resolver-a.txt",
                "--resolver-b", "resolver-b.txt", "--prefix-table", "prefixes.tsv",
                "--binary-dso", DSO, "--source-base-id", "830a9a31",
                "--mapping-schema-sha256", "a" * 64, "--map-part-prefix", "g5-map",
                "--map-manifest-out", "manifest.json", "--summary-out", "summary.json",
            ]))
            manifest = json.loads((built / "manifest.json").read_text())
            self.assertEqual(manifest["row_count"], 2)
            summary = json.loads((built / "summary.json").read_text())
            self.assertEqual(summary["mapping_schema_sha256"], "a" * 64)
            self.assertNotIn("instrument_sha256", summary)
            map_inputs = inputs / "map"
            record_inputs = inputs / "record"
            map_inputs.mkdir()
            record_inputs.mkdir()
            for source in built.iterdir():
                (map_inputs / source.name).write_bytes(source.read_bytes())
            binary = record_inputs / "cubrim"
            binary.write_bytes(b"ELF-test")
            binary.chmod(0o755)
            observed = binary.stat()
            (record_inputs / "perf.txt").write_text(perf_text(
                "100 0x400000 (/opt/cubrim+0x2000)"
            ))
            (record_inputs / "ids.txt").write_text(f"{BUILD_ID} {DSO}\n")
            g4.run_command(parser.parse_args([
                "reduce-record", "--input-root", str(inputs), "--output-root", str(reduced),
                "--map-manifest", "map/manifest.json", "--segments", "segments.tsv",
                "--page-size", "4096", "--perf-script", "record/perf.txt",
                "--build-id-list", "record/ids.txt", "--binary-dso", DSO,
                "--binary-build-id", BUILD_ID, "--binary-device", str(observed.st_dev),
                "--binary-inode", str(observed.st_ino), "--binary-path", "record/cubrim",
                "--binary-sha256", hashlib.sha256(b"ELF-test").hexdigest(),
                "--binary-size", "8", "--binary-stat-device", str(observed.st_dev),
                "--source-base-id", "830a9a31", "--instrument-sha256", "a" * 64,
                "--record-out", "record.json",
            ]))
            record = json.loads((reduced / "record.json").read_text())
            self.assertEqual(record["binary_sample_count"], 1)
            self.assertEqual(record["conservation"], "PASS")

    def test_regular_input_reader_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            victim = root / "victim"
            victim.write_text("secret\n", encoding="utf-8")
            linked = root / "input"
            linked.symlink_to(victim)
            with self.assertRaisesRegex(g4.MappingError, "symlink"):
                g4.read_regular_bytes(linked)

    def test_new_output_rejects_existing_symlink_and_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            victim = root / "victim"
            victim.write_bytes(b"SAFE")
            linked = root / "output"
            linked.symlink_to(victim)
            with self.assertRaisesRegex(g4.MappingError, "symlink"):
                g4.write_new_bytes(linked, b"changed")
            self.assertEqual(victim.read_bytes(), b"SAFE")
            with self.assertRaisesRegex(g4.MappingError, "traversal"):
                g4.validate_relative_artifact_name("../escape.tsv")

    def test_output_uses_unpredictable_temp_and_cleans_exact_temp_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            predictable = root / ".result.predictable.tmp"
            predictable.write_bytes(b"SAFE")
            g4.write_new_bytes(root / "result", b"done")
            self.assertEqual(predictable.read_bytes(), b"SAFE")
            self.assertEqual((root / "result").read_bytes(), b"done")
            with mock.patch.object(g4.os, "link", side_effect=OSError("injected")):
                with self.assertRaisesRegex(OSError, "injected"):
                    g4.write_new_bytes(root / "failed", b"x")
            self.assertFalse((root / "failed").exists())
            self.assertEqual(sorted(item.name for item in root.iterdir()), [
                ".result.predictable.tmp", "result"
            ])

    def test_declared_root_rejects_directory_symlink_fifo_and_escape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "real"
            real.mkdir()
            (real / "artifact").write_bytes(b"x")
            (root / "linked").symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(g4.MappingError, "symlink"):
                g4.resolve_contained_regular(root, "linked/artifact")
            fifo = root / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(g4.MappingError, "regular"):
                g4.resolve_contained_regular(root, "fifo")
            with self.assertRaisesRegex(g4.MappingError, "traversal"):
                g4.resolve_contained_regular(root, "../escape")

    def test_binary_snapshot_binds_hash_size_device_inode_and_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / "cubrim"
            binary.write_bytes(b"ELF-test")
            binary.chmod(0o755)
            observed = binary.stat()
            expected = g4.BinarySnapshot(
                sha256=hashlib.sha256(b"ELF-test").hexdigest(),
                size=8,
                device=observed.st_dev,
                inode=observed.st_ino,
                executable=True,
            )
            self.assertEqual(g4.verify_binary_snapshot(binary, expected), expected)
            link = Path(td) / "link"
            link.symlink_to(binary)
            with self.assertRaisesRegex(g4.MappingError, "symlink"):
                g4.verify_binary_snapshot(link, expected)

    def test_cli_contract_has_runner_owned_artifact_subcommands(self) -> None:
        parser = g4.make_parser()
        build = parser.parse_args([
            "build-map", "--input-root", "/in", "--output-root", "/out",
            "--segments", "g", "--sections", "s", "--objdump", "o",
            "--resolver-a", "a", "--resolver-b", "b", "--prefix-table", "p",
            "--binary-dso", DSO, "--map-part-prefix", "m", "--map-manifest-out", "manifest.json",
            "--summary-out", "sum.json",
            "--source-base-id", "830a9a31", "--mapping-schema-sha256", "a" * 64,
        ])
        self.assertEqual(build.command, "build-map")
        normalized = parser.parse_args([
            "normalize-elf", "--input-root", "/in", "--output-root", "/out",
            "--readelf-programs", "p", "--readelf-sections", "s",
            "--binary-sha256", "a" * 64, "--segments-out", "g.tsv",
            "--sections-out", "s.tsv", "--source-base-id", "830a9a31",
            "--instrument-sha256", "b" * 64, "--summary-out", "n.json",
        ])
        self.assertEqual(normalized.command, "normalize-elf")
        reduce = parser.parse_args([
            "reduce-record", "--input-root", "/in", "--output-root", "/out",
            "--map-manifest", "manifest.json", "--segments", "segments.tsv",
            "--page-size", "4096", "--perf-script", "perf",
            "--build-id-list", "ids", "--binary-dso", DSO,
            "--binary-build-id", BUILD_ID, "--binary-device", "08:01",
            "--binary-inode", "12345", "--record-out", "record.json",
            "--source-base-id", "830a9a31", "--instrument-sha256", "a" * 64,
            "--binary-path", "cubrim", "--binary-sha256", "b" * 64,
            "--binary-size", "8", "--binary-stat-device", "2049",
        ])
        self.assertEqual(reduce.command, "reduce-record")
        summarize = parser.parse_args([
            "summarize-file", "--input-root", "/in", "--output-root", "/out",
            "--cell", "dickens/max", "--record-a", "a.json",
            "--record-b", "b.json", "--summary-out", "file.json",
        ])
        self.assertEqual(summarize.command, "summarize-file")


if __name__ == "__main__":
    unittest.main(verbosity=2)
