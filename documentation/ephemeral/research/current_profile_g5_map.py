#!/usr/bin/env python3
"""Frozen-artifact, full-binary mapper for the NEW-24 G5 campaign."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import gzip
import hashlib
import io
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import zlib
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


class MappingError(ValueError):
    """A frozen input cannot satisfy the G5 contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MappingError(message)


def parse_hex(value: str, field: str) -> int:
    try:
        return int(value, 16)
    except ValueError as error:
        raise MappingError(f"invalid hexadecimal {field}: {value}") from error


def clean_field(value: str, field: str) -> str:
    require(bool(value) and not any(char in value for char in "\t\r\n"), f"unsafe {field}")
    return value


@dataclasses.dataclass(frozen=True)
class LoadSegment:
    name: str
    vaddr_start: int
    vaddr_end: int
    file_offset: int
    file_end: int
    alignment: int
    flags: str
    sha256: str


@dataclasses.dataclass(frozen=True)
class ExecutableSection:
    name: str
    vaddr_start: int
    vaddr_end: int
    file_offset: int
    flags: str
    sha256: str


@dataclasses.dataclass(frozen=True)
class Frame:
    function: str
    file: str
    line: int


@dataclasses.dataclass(frozen=True)
class Instruction:
    address: int
    byte_length: int
    section: str
    raw_symbol: str
    raw_symbol_start: int | None

    @property
    def raw_symbol_offset(self) -> str:
        return "NA" if self.raw_symbol_start is None else f"0x{self.address - self.raw_symbol_start:x}"


@dataclasses.dataclass(frozen=True)
class PrefixRule:
    source_domain: str
    package_identity: str
    prefix: str
    replacement: str


@dataclasses.dataclass(frozen=True)
class InstructionRow:
    instruction_vma: int
    dso_file_offset: int
    segment: str
    section: str
    raw_symbol: str
    raw_symbol_offset: str
    emitted_family: str
    frames: tuple[Frame, ...]
    source_family: str
    source_provenance_json: str
    resolution_status: str
    dso: str


@dataclasses.dataclass(frozen=True)
class BinaryIdentity:
    dso: str
    build_id: str
    device: str
    inode: int


@dataclasses.dataclass(frozen=True)
class BinarySnapshot:
    sha256: str
    size: int
    device: int
    inode: int
    executable: bool


@dataclasses.dataclass(frozen=True)
class ExecutableSegmentIdentity:
    file_offset: int
    vaddr: int
    file_size: int
    memory_size: int
    alignment: int


@dataclasses.dataclass(frozen=True)
class OtherDsoSnapshot:
    path: str
    build_id: str
    sha256: str
    size: int
    device: int
    inode: int
    mtime_ns: int
    ctime_ns: int
    executable_segments: tuple[ExecutableSegmentIdentity, ...]


@dataclasses.dataclass(frozen=True)
class MMap2:
    start: int
    length: int
    pgoff: int
    union_mode: str
    union_identity: str
    protection: str
    dso: str

    @property
    def end(self) -> int:
        return self.start + self.length


@dataclasses.dataclass(frozen=True)
class PerfSample:
    period: int
    ip: int
    dso: str
    dsoff: int


SEGMENT_HEADER = ("segment", "vaddr_start", "vaddr_end", "file_offset", "file_end", "alignment", "flags", "sha256")
SECTION_HEADER = ("section", "vaddr_start", "vaddr_end", "file_offset", "flags", "sha256")
PREFIX_HEADER = ("source_domain", "package_identity", "prefix", "replacement")
MAP_HEADER = (
    "instruction_vma", "dso_file_offset", "segment", "section", "raw_symbol",
    "raw_symbol_offset", "emitted_family", "frame_stack_json", "source_family", "source_provenance_json",
    "resolution_status", "dso",
)
OBJDUMP_SECTION_RE = re.compile(r"^Disassembly of section ([^:]+):\s*$")
OBJDUMP_SYMBOL_RE = re.compile(r"^\s*([0-9A-Fa-f]+) <(.+)>:\s*$")
OBJDUMP_INSTRUCTION_RE = re.compile(r"^\s*([0-9A-Fa-f]+):\s+((?:[0-9A-Fa-f]{2}(?:\s+|$))+)(?:.*)$")
ADDRESS_RE = re.compile(r"^0x([0-9A-Fa-f]+)$")
FILE_LINE_RE = re.compile(r"^(.*):(\d+)(?:\s+.*)?$")
BUILD_MMAP_RE = re.compile(
    r"^PERF_RECORD_MMAP2\s+\d+/\d+:\s+\[(0x[0-9A-Fa-f]+)\((0x[0-9A-Fa-f]+)\)\s+@\s+"
    r"(0x[0-9A-Fa-f]+)\s+<([0-9A-Fa-f]+)>\]:\s+(\S+)\s+(.+)$"
)
DEVICE_MMAP_RE = re.compile(
    r"^PERF_RECORD_MMAP2\s+\d+/\d+:\s+\[(0x[0-9A-Fa-f]+)\((0x[0-9A-Fa-f]+)\)\s+@\s+"
    r"(0x[0-9A-Fa-f]+)\s+([^\s]+\s+\d+\s+\d+)\]:\s+(\S+)\s+(.+)$"
)
SAMPLE_RE = re.compile(r"^\s*(\d+)\s+(0x[0-9A-Fa-f]+|[0-9A-Fa-f]+)\s+\((.+)\+(0x[0-9A-Fa-f]+|[0-9A-Fa-f]+)\)\s*$")
LOST_RE = re.compile(r"PERF_RECORD_LOST|\blost(?:[-_ ](?:record|sample)s?)?\b", re.I)
BUILD_ID_RE = re.compile(r"^([0-9A-Fa-f]{8,128})\s+(.+)$")
KERNEL_DSOS = frozenset({"[kernel.kallsyms]", "[kallsyms]"})
PSEUDO_DSOS = frozenset({"[vdso]", "[vsyscall]"})


def _parse_ranges(text: str, header: tuple[str, ...], segment: bool) -> list[Any]:
    with io.StringIO(text) as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(tuple(reader.fieldnames or ()) == header, f"{'PT_LOAD' if segment else 'executable section'} schema mismatch")
        result: list[Any] = []
        names: set[str] = set()
        for line, row in enumerate(reader, 2):
            key = "segment" if segment else "section"
            name = clean_field(row[key], f"{key} name at line {line}")
            require(name not in names, f"duplicate {key}: {name}")
            names.add(name)
            start, end = parse_hex(row["vaddr_start"], "range start"), parse_hex(row["vaddr_end"], "range end")
            fstart = parse_hex(row["file_offset"], "file offset")
            flags, digest = clean_field(row["flags"], "flags"), row["sha256"]
            require(start < end, f"empty executable range: {name}")
            require(("E" in flags if segment else "X" in flags), f"non-executable range: {name}")
            require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"invalid SHA-256: {name}")
            if segment:
                fend = parse_hex(row["file_end"], "file end")
                alignment = parse_hex(row["alignment"], "alignment")
                require(fstart < fend and end - start == fend - fstart, f"PT_LOAD file/VMA extent mismatch: {name}")
                result.append(LoadSegment(name, start, end, fstart, fend, alignment, flags, digest))
            else:
                result.append(ExecutableSection(name, start, end, fstart, flags, digest))
    require(result, "empty executable universe")
    result.sort(key=lambda item: (item.vaddr_start, item.vaddr_end, item.name))
    for previous, current in zip(result, result[1:]):
        require(previous.vaddr_end <= current.vaddr_start, f"overlapping {'PT_LOAD VMA' if segment else 'executable'} ranges: {previous.name} and {current.name}")
    if segment:
        by_file = sorted(result, key=lambda item: (item.file_offset, item.file_end))
        for previous, current in zip(by_file, by_file[1:]):
            require(previous.file_end <= current.file_offset, f"overlapping PT_LOAD file ranges: {previous.name} and {current.name}")
    return result


def parse_load_segments(text: str) -> list[LoadSegment]:
    return _parse_ranges(text, SEGMENT_HEADER, True)


def parse_executable_sections(text: str) -> list[ExecutableSection]:
    return _parse_ranges(text, SECTION_HEADER, False)


READELF_LOAD_RE = re.compile(
    r"^LOAD\s+(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)\s+0x[0-9A-Fa-f]+\s+"
    r"(0x[0-9A-Fa-f]+)\s+0x[0-9A-Fa-f]+\s+([RWE ]+?)\s+(0x[0-9A-Fa-f]+)$"
)
READELF_SECTION_RE = re.compile(
    r"^\s*\[\s*(\d+)\]\s+(\S+)\s+\S+\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+"
    r"([0-9A-Fa-f]+)\s+\S+\s+([A-Z]*)\s+\d+\s+\d+\s+\d+\s*$"
)
OTHER_DSO_LOAD_RE = re.compile(
    r"^LOAD\s+(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)\s+0x[0-9A-Fa-f]+\s+"
    r"(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)\s+([RWE ]+?)\s+(0x[0-9A-Fa-f]+)$"
)
READELF_BUILD_ID_RE = re.compile(r"\bBuild ID:\s*([0-9A-Fa-f]{8,128})\s*$")


def _render_segments(segments: Sequence[LoadSegment]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(SEGMENT_HEADER)
    for item in segments:
        writer.writerow((item.name, f"0x{item.vaddr_start:x}", f"0x{item.vaddr_end:x}",
                         f"0x{item.file_offset:x}", f"0x{item.file_end:x}",
                         f"0x{item.alignment:x}", item.flags, item.sha256))
    return output.getvalue()


def _render_sections(sections: Sequence[ExecutableSection]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(SECTION_HEADER)
    for item in sections:
        writer.writerow((item.name, f"0x{item.vaddr_start:x}", f"0x{item.vaddr_end:x}",
                         f"0x{item.file_offset:x}", item.flags, item.sha256))
    return output.getvalue()


def normalize_readelf(program_headers: str, section_headers: str, binary_sha256: str) -> tuple[str, str]:
    """Normalize frozen GNU ``readelf -W -l/-S`` output without shell parsing."""
    require(re.fullmatch(r"[0-9a-f]{64}", binary_sha256) is not None,
            "invalid binary SHA-256")
    require("Program Headers:" in program_headers and
            "Type" in program_headers and "VirtAddr" in program_headers and
            "FileSiz" in program_headers,
            "GNU readelf program-header schema/locale mismatch")
    segments: list[LoadSegment] = []
    for raw in program_headers.splitlines():
        line = raw.strip()
        if not line.startswith("LOAD"):
            continue
        match = READELF_LOAD_RE.fullmatch(line)
        require(match is not None, f"malformed GNU readelf LOAD row: {line}")
        offset_s, vaddr_s, filesz_s, flags, align_s = match.groups()
        if "E" not in flags:
            continue
        offset, vaddr, filesz = int(offset_s, 16), int(vaddr_s, 16), int(filesz_s, 16)
        require(filesz > 0, "empty executable GNU readelf LOAD row")
        segments.append(LoadSegment(
            f"LOAD{len(segments)}", vaddr, vaddr + filesz, offset, offset + filesz,
            int(align_s, 16), " ".join(flags.split()), binary_sha256,
        ))
    segment_text = _render_segments(segments)
    # Reparse to apply overlap, uniqueness, and extent checks to normalized data.
    parsed_segments = parse_load_segments(segment_text)

    require("Section Headers:" in section_headers and "[Nr]" in section_headers and
            "Address" in section_headers and "Flg" in section_headers,
            "GNU readelf section-header schema/locale mismatch")
    sections: list[ExecutableSection] = []
    for raw in section_headers.splitlines():
        match = READELF_SECTION_RE.fullmatch(raw)
        if match is None:
            if " AX " in f" {raw} " and raw.lstrip().startswith("["):
                raise MappingError(f"malformed GNU readelf executable section row: {raw.strip()}")
            continue
        _index, name, address_s, offset_s, size_s, flags = match.groups()
        if "X" not in flags:
            continue
        address, offset, size = int(address_s, 16), int(offset_s, 16), int(size_s, 16)
        require(size > 0, f"empty executable GNU readelf section: {name}")
        sections.append(ExecutableSection(name, address, address + size, offset, flags, binary_sha256))
    section_text = _render_sections(sections)
    parsed_sections = parse_executable_sections(section_text)
    for section in parsed_sections:
        segment, converted = vma_to_dso_offset(parsed_segments, section.vaddr_start,
                                                section.vaddr_end - section.vaddr_start)
        require(converted == section.file_offset,
                f"section/PT_LOAD file-offset mismatch: {section.name} in {segment.name}")
    return segment_text, section_text


def vma_to_dso_offset(segments: Sequence[LoadSegment], vma: int, length: int = 1) -> tuple[LoadSegment, int]:
    matches = [item for item in segments if item.vaddr_start <= vma and vma + length <= item.vaddr_end]
    require(len(matches) == 1, f"instruction outside unique executable PT_LOAD: 0x{vma:x}")
    item = matches[0]
    offset = item.file_offset + vma - item.vaddr_start
    require(offset + length <= item.file_end, f"instruction exceeds PT_LOAD file range: 0x{vma:x}")
    require(dso_offset_to_vma(segments, offset, length) == vma, f"PT_LOAD reverse conversion mismatch: 0x{vma:x}")
    return item, offset


def dso_offset_to_vma(segments: Sequence[LoadSegment], offset: int, length: int = 1) -> int:
    matches = [item for item in segments if item.file_offset <= offset and offset + length <= item.file_end]
    require(len(matches) == 1, f"DSO offset outside unique executable PT_LOAD: 0x{offset:x}")
    item = matches[0]
    return item.vaddr_start + offset - item.file_offset


def section_for_address(sections: Sequence[ExecutableSection], address: int, length: int = 1) -> ExecutableSection:
    matches = [item for item in sections if item.vaddr_start <= address and address + length <= item.vaddr_end]
    require(len(matches) == 1, f"instruction outside executable section: 0x{address:x}")
    return matches[0]


def parse_objdump(text: str, sections: Sequence[ExecutableSection]) -> list[Instruction]:
    declared = {item.name for item in sections}
    current: str | None = None
    symbol, symbol_start = "raw_symbol_unresolved", None
    result: list[Instruction] = []
    seen: set[int] = set()
    for number, line in enumerate(text.splitlines(), 1):
        if match := OBJDUMP_SECTION_RE.fullmatch(line):
            current, symbol, symbol_start = match.group(1), "raw_symbol_unresolved", None
        elif match := OBJDUMP_SYMBOL_RE.fullmatch(line):
            symbol_start, symbol = int(match.group(1), 16), clean_field(match.group(2), "raw symbol")
        elif match := OBJDUMP_INSTRUCTION_RE.fullmatch(line):
            require(current in declared, f"instruction from undeclared executable section at objdump line {number}")
            address = int(match.group(1), 16)
            length = len(re.findall(r"[0-9A-Fa-f]{2}", match.group(2)))
            require(address not in seen, f"duplicate instruction address 0x{address:x}")
            seen.add(address)
            section = section_for_address(sections, address, length)
            require(section.name == current, f"objdump section/address mismatch at 0x{address:x}")
            require(symbol_start is None or address >= symbol_start, f"instruction precedes raw symbol at 0x{address:x}")
            result.append(Instruction(address, length, current, symbol, symbol_start))
    require(result, "empty executable instruction universe")
    result.sort(key=lambda item: item.address)
    for previous, current in zip(result, result[1:]):
        require(previous.address + previous.byte_length <= current.address, f"overlapping decoded instructions at 0x{current.address:x}")
    return result


def parse_resolver(text: str) -> dict[int, tuple[Frame, ...]]:
    result: dict[int, tuple[Frame, ...]] = {}
    current: int | None = None
    pending: list[str] = []

    def finish() -> None:
        nonlocal pending
        if current is None:
            require(not pending, "resolver content before first address")
            return
        require(len(pending) % 2 == 0, f"incomplete resolver frame at 0x{current:x}")
        frames: list[Frame] = []
        for index in range(0, len(pending), 2):
            function = clean_field(pending[index], "resolver function")
            location = pending[index + 1]
            if location.endswith(":?"):
                file = location[:-2]
                require(file not in {"", "?"}, f"malformed resolver location at 0x{current:x}")
                frames.append(Frame(function, clean_field(file, "resolver file"), 0))
                continue
            match = FILE_LINE_RE.fullmatch(location)
            require(match is not None, f"malformed resolver location at 0x{current:x}")
            frames.append(Frame(function, match.group(1), int(match.group(2))))
        require(current not in result, f"duplicate resolver address 0x{current:x}")
        result[current] = tuple(frames)
        pending = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if match := ADDRESS_RE.fullmatch(line):
            finish()
            current = int(match.group(1), 16)
        else:
            pending.append(line)
    finish()
    require(result, "empty resolver stream")
    return result


def parse_prefix_table(text: str) -> list[PrefixRule]:
    with io.StringIO(text) as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(tuple(reader.fieldnames or ()) == PREFIX_HEADER, "prefix table schema mismatch")
        result: list[PrefixRule] = []
        seen: set[str] = set()
        for line, row in enumerate(reader, 2):
            domain = clean_field(row["source_domain"], f"source domain at line {line}")
            package = clean_field(row["package_identity"], f"package identity at line {line}")
            prefix = clean_field(row["prefix"], f"prefix at line {line}")
            replacement = clean_field(row["replacement"], f"replacement at line {line}")
            require(prefix.startswith("/") and ".." not in PurePosixPath(prefix).parts, f"unsafe prefix path: {prefix}")
            require(replacement.startswith("$") and "/" not in replacement and ".." not in replacement, f"unsafe prefix replacement: {replacement}")
            require(prefix not in seen, f"duplicate prefix: {prefix}")
            seen.add(prefix)
            result.append(PrefixRule(domain, package, prefix.rstrip("/") or "/", replacement))
    require(result, "empty prefix table")
    return sorted(result, key=lambda item: (-len(item.prefix), item.prefix))


def normalize_source(path: str, rules: Sequence[PrefixRule]) -> tuple[str, PrefixRule]:
    require(
        path.startswith("/") and not any(ord(char) < 32 or ord(char) == 127 for char in path),
        f"unsafe resolver source path: {path}",
    )

    def under_prefix(candidate: str, prefix: str) -> bool:
        return prefix == "/" or candidate == prefix or candidate.startswith(prefix + "/")

    raw_rule = next((rule for rule in rules if under_prefix(path, rule.prefix)), None)
    if raw_rule is None:
        raise MappingError(f"resolver source has no frozen prefix: {path}")

    parts: list[str] = []
    for part in path.split("/")[1:]:
        if part in {"", "."}:
            continue
        if part == "..":
            require(bool(parts), f"resolver source path escapes root: {path}")
            parts.pop()
            continue
        parts.append(part)
    normalized = "/" + "/".join(parts)
    require(
        under_prefix(normalized, raw_rule.prefix),
        f"resolver source path escapes frozen prefix {raw_rule.prefix}: {path}",
    )
    return raw_rule.replacement + normalized[len(raw_rule.prefix):], raw_rule


def frame_json(frames: Sequence[Frame]) -> str:
    return json.dumps([dataclasses.asdict(item) for item in frames], sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def provenance_for(frames: Sequence[Frame], raw_symbol: str, rules: Sequence[PrefixRule]) -> tuple[str, str, str]:
    if not frames or frames[0].function == "??" or frames[0].file == "??" or frames[0].line == 0:
        return "special:binary_unresolved", "{}", "binary_unresolved"
    inner = frames[0]
    normalized, rule = normalize_source(inner.file, rules)
    value = {
        "source_domain": rule.source_domain,
        "package_identity": rule.package_identity,
        "normalized_path": normalized,
        "innermost_item": clean_field(inner.function, "innermost item"),
        "source_location": {"line": inner.line},
        "raw_outer_symbol": raw_symbol,
        "frame_stack_sha256": hashlib.sha256(frame_json(frames).encode()).hexdigest(),
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sf:" + hashlib.sha256(encoded.encode()).hexdigest(), encoded, "resolved"


def emitted_family_for(raw_symbol: str) -> str:
    provenance = json.dumps({"raw_outer_symbol": raw_symbol}, sort_keys=True,
                            separators=(",", ":"), ensure_ascii=True)
    return "ef:" + hashlib.sha256(provenance.encode()).hexdigest()


def build_family_reverse_index(rows: Sequence[InstructionRow]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.source_family == "special:binary_unresolved":
            require(row.source_provenance_json == "{}", "binary-unresolved provenance mismatch")
            result[row.source_family] = {"classification": "binary_unresolved"}
            continue
        try:
            parsed = json.loads(row.source_provenance_json)
        except json.JSONDecodeError as error:
            raise MappingError("invalid source-family provenance") from error
        canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        expected = "sf:" + hashlib.sha256(canonical.encode()).hexdigest()
        require(row.source_family == expected, "source-family key collision or invalid provenance hash")
        previous = result.get(row.source_family)
        require(previous is None or previous == parsed, "source-family key collision")
        result[row.source_family] = parsed
    return result


def build_emitted_reverse_index(rows: Sequence[InstructionRow]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        provenance = {"raw_outer_symbol": row.raw_symbol}
        expected = emitted_family_for(row.raw_symbol)
        require(row.emitted_family == expected, "emitted-family key collision or invalid provenance hash")
        previous = result.get(row.emitted_family)
        require(previous is None or previous == provenance, "emitted-family key collision")
        result[row.emitted_family] = provenance
    return result


def build_instruction_rows(segments_text: str, sections_text: str, objdump_text: str, resolver_a_text: str, resolver_b_text: str, prefix_text: str, binary_dso: str) -> list[InstructionRow]:
    require(binary_dso.startswith("/"), "binary DSO must be absolute")
    segments, sections = parse_load_segments(segments_text), parse_executable_sections(sections_text)
    instructions = parse_objdump(objdump_text, sections)
    resolver_a, resolver_b = parse_resolver(resolver_a_text), parse_resolver(resolver_b_text)
    addresses = {item.address for item in instructions}
    require(set(resolver_a) == addresses and set(resolver_b) == addresses, "resolver address coverage does not match instruction universe")
    rules = parse_prefix_table(prefix_text)
    rows: list[InstructionRow] = []
    offsets: set[int] = set()
    for item in instructions:
        frames = resolver_a[item.address]
        require(frames == resolver_b[item.address], f"conflicting ordered frame stacks at 0x{item.address:x}")
        segment, offset = vma_to_dso_offset(segments, item.address, item.byte_length)
        section = section_for_address(sections, item.address, item.byte_length)
        require(section.file_offset + item.address - section.vaddr_start == offset, f"section/PT_LOAD file-offset mismatch at 0x{item.address:x}")
        require(offset not in offsets, f"duplicate canonical DSO offset 0x{offset:x}")
        offsets.add(offset)
        family, provenance, status = provenance_for(frames, item.raw_symbol, rules)
        rows.append(InstructionRow(item.address, offset, segment.name, item.section, item.raw_symbol, item.raw_symbol_offset, emitted_family_for(item.raw_symbol), frames, family, provenance, status, binary_dso))
    build_family_reverse_index(rows)
    build_emitted_reverse_index(rows)
    return rows


def render_instruction_map(rows: Iterable[InstructionRow]) -> str:
    ordered = sorted(rows, key=lambda item: item.dso_file_offset)
    require(ordered, "cannot render empty instruction map")
    build_family_reverse_index(ordered)
    build_emitted_reverse_index(ordered)
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(MAP_HEADER)
    seen_vma: set[int] = set()
    seen_offsets: set[int] = set()
    for row in ordered:
        require(row.instruction_vma not in seen_vma, f"duplicate instruction VMA 0x{row.instruction_vma:x}")
        require(row.dso_file_offset not in seen_offsets, f"duplicate canonical DSO offset 0x{row.dso_file_offset:x}")
        seen_vma.add(row.instruction_vma)
        seen_offsets.add(row.dso_file_offset)
        writer.writerow((f"0x{row.instruction_vma:016x}", f"0x{row.dso_file_offset:016x}", row.segment, row.section, row.raw_symbol, row.raw_symbol_offset, row.emitted_family, frame_json(row.frames), row.source_family, row.source_provenance_json, row.resolution_status, row.dso))
    return output.getvalue()


def parse_instruction_map(text: str) -> list[InstructionRow]:
    with io.StringIO(text) as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(tuple(reader.fieldnames or ()) == MAP_HEADER, "instruction map schema mismatch")
        result: list[InstructionRow] = []
        for line, row in enumerate(reader, 2):
            try:
                raw_frames = json.loads(row["frame_stack_json"])
                frames = tuple(Frame(str(item["function"]), str(item["file"]), int(item["line"])) for item in raw_frames)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise MappingError(f"invalid frame stack at map line {line}") from error
            result.append(InstructionRow(parse_hex(row["instruction_vma"], "instruction VMA"), parse_hex(row["dso_file_offset"], "DSO file offset"), row["segment"], row["section"], row["raw_symbol"], row["raw_symbol_offset"], row["emitted_family"], frames, row["source_family"], row["source_provenance_json"], row["resolution_status"], row["dso"]))
    require(result, "empty instruction map")
    require(render_instruction_map(result) == text, "instruction map is not canonical")
    return result


def deterministic_gzip(payload: bytes) -> bytes:
    return gzip.compress(payload, compresslevel=9, mtime=0)


def decompress_single_gzip(compressed: bytes, *, max_bytes: int = 512 * 1024 * 1024) -> bytes:
    require(compressed[:2] == b"\x1f\x8b" and compressed[4:8] == b"\0\0\0\0", "invalid deterministic gzip header")
    stream = zlib.decompressobj(wbits=31)
    try:
        payload = stream.decompress(compressed, max_bytes + 1)
    except zlib.error as error:
        raise MappingError("invalid gzip stream") from error
    require(len(payload) <= max_bytes, "gzip decompression limit exceeded")
    require(stream.eof, "truncated gzip stream")
    require(not stream.unused_data and not stream.unconsumed_tail, "extra gzip member or trailing bytes")
    return payload


def gzip_evidence(uncompressed: bytes, compressed: bytes) -> dict[str, Any]:
    require(decompress_single_gzip(compressed, max_bytes=len(uncompressed)) == uncompressed, "gzip decompression check failed")
    return {"uncompressed_bytes": len(uncompressed), "uncompressed_sha256": hashlib.sha256(uncompressed).hexdigest(), "compressed_bytes": len(compressed), "compressed_sha256": hashlib.sha256(compressed).hexdigest(), "gzip_mtime": 0, "gzip_compresslevel": 9}


def split_instruction_map(
    rows: Sequence[InstructionRow], *, max_rows: int = 1_000_000,
    max_compressed_bytes: int = 90_000_000, part_prefix: str = "map",
) -> tuple[list[bytes], dict[str, Any]]:
    require(max_rows > 0, "max rows must be positive")
    require(0 < max_compressed_bytes <= 90_000_000, "invalid compressed part byte limit")
    validate_relative_artifact_name(part_prefix)
    canonical_rows = sorted(rows, key=lambda item: item.dso_file_offset)
    full = render_instruction_map(canonical_rows).encode()
    lines = full.splitlines(keepends=True)
    require(len(lines) == len(canonical_rows) + 1, "canonical map row/line mismatch")
    parts: list[bytes] = []
    evidence: list[dict[str, Any]] = []
    start = 0
    while start < len(canonical_rows):
        end = min(len(canonical_rows), start + max_rows)
        prefix = lines[0] if start == 0 else b""
        payload = prefix + b"".join(lines[start + 1:end + 1])
        compressed = deterministic_gzip(payload)
        while len(compressed) > max_compressed_bytes and end - start > 1:
            end = start + (end - start) // 2
            payload = prefix + b"".join(lines[start + 1:end + 1])
            compressed = deterministic_gzip(payload)
        require(len(compressed) <= max_compressed_bytes,
                f"single map row exceeds compressed part limit at row {start}")
        group = canonical_rows[start:end]
        index = len(parts)
        path = f"{part_prefix}.part-{index:05d}.tsv.gz"
        part = {"part_index": index, "path": path, "first_dso_file_offset": group[0].dso_file_offset, "last_dso_file_offset": group[-1].dso_file_offset, "first_row_index": start, "last_row_index": end - 1, "row_count": len(group), **gzip_evidence(payload, compressed)}
        parts.append(compressed)
        evidence.append(part)
        start = end
    manifest = {"schema": "cubr-new24-g5-map-parts-v1", "part_count": len(parts), "row_count": len(canonical_rows), "full_uncompressed_bytes": len(full), "full_uncompressed_sha256": hashlib.sha256(full).hexdigest(), "parts": evidence}
    return parts, manifest


def verify_map_parts(parts: Sequence[bytes], manifest: Mapping[str, Any]) -> bytes:
    declared = manifest.get("parts")
    require(isinstance(declared, list) and len(parts) == manifest.get("part_count") == len(declared), "map part count mismatch")
    payloads: list[bytes] = []
    rows: list[InstructionRow] = []
    previous_offset: int | None = None
    seen_paths: set[str] = set()
    for index, (compressed, item) in enumerate(zip(parts, declared)):
        require(item.get("part_index") == index, "map part index mismatch")
        payload = decompress_single_gzip(compressed, max_bytes=int(item["uncompressed_bytes"]))
        observed_evidence = gzip_evidence(payload, compressed)
        try:
            declared_evidence = {key: item[key] for key in observed_evidence}
        except KeyError as error:
            raise MappingError("map part evidence is incomplete") from error
        require(observed_evidence == declared_evidence, "map part evidence mismatch")
        require(item.get("path") == f"{PurePosixPath(str(item.get('path'))).name}" and
                re.fullmatch(r".+\.part-\d{5}\.tsv\.gz", str(item.get("path"))) is not None,
                "unsafe or nonnumeric map part path")
        require(str(item["path"]) not in seen_paths, "duplicate map part path")
        seen_paths.add(str(item["path"]))
        parse_payload = payload if index == 0 else ("\t".join(MAP_HEADER) + "\n").encode() + payload
        parsed = parse_instruction_map(parse_payload.decode())
        require(len(parsed) == item["row_count"], "map part row-count mismatch")
        require(parsed[0].dso_file_offset == item["first_dso_file_offset"] and parsed[-1].dso_file_offset == item["last_dso_file_offset"], "map part DSO-offset range mismatch")
        require(item["first_row_index"] == len(rows) and item["last_row_index"] == len(rows) + len(parsed) - 1, "map part row range is not contiguous")
        require(previous_offset is None or previous_offset < parsed[0].dso_file_offset, "map part ranges overlap or are unordered")
        previous_offset = parsed[-1].dso_file_offset
        rows.extend(parsed)
        payloads.append(payload)
    full = b"".join(payloads)
    require(full == render_instruction_map(rows).encode(), "ordered part concatenation is not canonical map")
    require(len(rows) == manifest.get("row_count") and len(full) == manifest.get("full_uncompressed_bytes") and hashlib.sha256(full).hexdigest() == manifest.get("full_uncompressed_sha256"), "full map reconstruction mismatch")
    return full


def parse_build_id_list(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        match = BUILD_ID_RE.fullmatch(line)
        require(match is not None, f"malformed build-ID line {number}")
        build_id, dso = match.groups()
        require(dso not in result, f"duplicate build-ID DSO: {dso}")
        result[dso] = build_id.lower()
    require(result, "empty build-ID list")
    return result


def parse_perf_script(text: str) -> tuple[list[MMap2], list[PerfSample]]:
    mappings: list[MMap2] = []
    samples: list[PerfSample] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if LOST_RE.search(line):
            raise MappingError(f"lost record in perf script at line {number}")
        match = BUILD_MMAP_RE.fullmatch(line)
        mode = "build_id"
        if match is None:
            match = DEVICE_MMAP_RE.fullmatch(line)
            mode = "device_inode"
        if match:
            start, length, pgoff, union, protection, dso = match.groups()
            mappings.append(MMap2(parse_hex(start, "MMAP2 start"), parse_hex(length, "MMAP2 length"), parse_hex(pgoff, "MMAP2 pgoff"), mode, union.lower(), protection, dso))
            continue
        match = SAMPLE_RE.fullmatch(line)
        require(match is not None, f"unrecognized perf-script line {number}: {line}")
        period, ip, dso, dsoff = match.groups()
        require(int(period) > 0, f"non-positive sample period at line {number}")
        samples.append(PerfSample(int(period), parse_hex(ip, "sample IP"), dso, parse_hex(dsoff, "sample dsoff")))
    require(samples, "perf script contains no samples")
    return mappings, samples


def empty_aggregate() -> dict[str, int | float]:
    return {"sample_count": 0, "sum_period": 0, "sum_period_squared": 0, "share_percent": 0.0}


def add_period(aggregate: dict[str, int | float], period: int) -> None:
    aggregate["sample_count"] = int(aggregate["sample_count"]) + 1
    aggregate["sum_period"] = int(aggregate["sum_period"]) + period
    aggregate["sum_period_squared"] = int(aggregate["sum_period_squared"]) + period * period


def validate_conservation(families: Mapping[str, Mapping[str, int | float]], count: int, period: int, squared: int) -> None:
    require(sum(int(item["sample_count"]) for item in families.values()) == count, "sample-count conservation failure")
    require(sum(int(item["sum_period"]) for item in families.values()) == period, "period conservation failure")
    require(sum(int(item["sum_period_squared"]) for item in families.values()) == squared, "squared-period conservation failure")


def zero_hit_upper_bound(binary_sample_count: int, simultaneous_records: int = 6) -> float | None:
    require(binary_sample_count >= 0, "binary sample count must be nonnegative")
    require(simultaneous_records > 0, "simultaneous record count must be positive")
    if binary_sample_count == 0:
        return None
    return 1.0 - (0.05 / simultaneous_records) ** (1.0 / binary_sample_count)


def _align_down(value: int, alignment: int) -> int:
    return value - value % alignment


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _validate_exact_binary_mmap(
    mapping: MMap2, segments: Sequence[LoadSegment], identity: BinaryIdentity,
    page_size: int,
) -> None:
    require(page_size > 0 and page_size & (page_size - 1) == 0,
            "invalid frozen page size")
    require(len(segments) == 1, "expected exactly one executable PT_LOAD")
    segment = segments[0]
    require(segment.file_offset % page_size == segment.vaddr_start % page_size,
            "executable PT_LOAD offset/VMA page incongruence")
    expected_pgoff = _align_down(segment.file_offset, page_size)
    leading = segment.vaddr_start - _align_down(segment.vaddr_start, page_size)
    expected_length = _align_up(leading + segment.file_end - segment.file_offset, page_size)
    require(mapping.pgoff == expected_pgoff and mapping.length == expected_length,
            "exact binary MMAP2 file range mismatch")
    require(mapping.start % page_size == 0 and
            (mapping.start - _align_down(segment.vaddr_start, page_size)) % page_size == 0,
            "exact binary MMAP2 load bias mismatch")
    require(mapping.union_mode == "build_id",
            "exact binary MMAP2 must use build-ID union")
    require(mapping.union_identity == identity.build_id.lower(),
            "exact binary MMAP2 build ID mismatch")
    require(mapping.protection == "r-xp", "exact binary MMAP2 protection mismatch")


def _canonical_absolute_dso(dso: str) -> bool:
    if not dso.startswith("/") or any(ord(char) < 32 or ord(char) == 127 for char in dso):
        return False
    parts = PurePosixPath(dso).parts
    return ".." not in parts and "." not in parts and "//" not in dso


def _canonical_other_dso_path(path: Path) -> tuple[Path, os.stat_result]:
    rendered = str(path)
    require(_canonical_absolute_dso(rendered), "other DSO path is not canonical absolute")
    current = Path("/")
    try:
        for component in PurePosixPath(rendered).parts[1:]:
            current /= component
            info = current.lstat()
            require(not stat.S_ISLNK(info.st_mode), f"other DSO path component is a symlink: {current}")
        final = path.lstat()
    except FileNotFoundError as error:
        raise MappingError(f"missing other DSO: {path}") from error
    require(stat.S_ISREG(final.st_mode), f"other DSO is not a regular file: {path}")
    require(str(path.resolve(strict=True)) == rendered, "other DSO path is not canonical absolute")
    return path, final


def _other_dso_snapshot(path: Path, expected_build_id: str | None) -> OtherDsoSnapshot:
    canonical, path_stat = _canonical_other_dso_path(path)
    if expected_build_id is not None:
        require(re.fullmatch(r"[0-9A-Fa-f]{8,128}", expected_build_id) is not None,
                "invalid expected other DSO build ID")
    descriptor = os.open(canonical, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), f"other DSO is not a regular file: {path}")
        require((before.st_dev, before.st_ino) == (path_stat.st_dev, path_stat.st_ino),
                "other DSO identity changed before authentication")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        os.lseek(descriptor, 0, os.SEEK_SET)
        completed = subprocess.run(
            ["/usr/bin/readelf", "-W", "-n", "-l", f"/proc/self/fd/{descriptor}"],
            check=False, capture_output=True, text=True, pass_fds=(descriptor,),
            env={**os.environ, "LC_ALL": "C"},
        )
        require(completed.returncode == 0,
                f"GNU readelf rejected other DSO: {completed.stderr.strip()}")
        build_ids = [match.group(1).lower() for line in completed.stdout.splitlines()
                     if (match := READELF_BUILD_ID_RE.search(line))]
        require(len(build_ids) == 1, "other DSO must contain exactly one GNU build ID")
        segments: list[ExecutableSegmentIdentity] = []
        for raw in completed.stdout.splitlines():
            line = raw.strip()
            if not line.startswith("LOAD"):
                continue
            match = OTHER_DSO_LOAD_RE.fullmatch(line)
            require(match is not None, f"malformed GNU readelf LOAD row for other DSO: {line}")
            offset_s, vaddr_s, filesz_s, memsz_s, flags, align_s = match.groups()
            if "E" not in flags:
                continue
            file_size, memory_size = int(filesz_s, 16), int(memsz_s, 16)
            require(file_size > 0 and memory_size >= file_size,
                    "invalid executable PT_LOAD in other DSO")
            segments.append(ExecutableSegmentIdentity(
                int(offset_s, 16), int(vaddr_s, 16), file_size, memory_size,
                int(align_s, 16),
            ))
        require(bool(segments), "other DSO has no executable PT_LOAD")
        after = os.fstat(descriptor)
        stable_before = (before.st_dev, before.st_ino, before.st_size,
                         before.st_mtime_ns, before.st_ctime_ns)
        stable_after = (after.st_dev, after.st_ino, after.st_size,
                        after.st_mtime_ns, after.st_ctime_ns)
        require(stable_before == stable_after and size == after.st_size,
                "other DSO changed during authentication")
        build_id = build_ids[0]
        if expected_build_id is not None:
            require(build_id == expected_build_id.lower(), "other DSO build ID mismatch")
        return OtherDsoSnapshot(
            str(canonical), build_id, digest.hexdigest(), size, after.st_dev,
            after.st_ino, after.st_mtime_ns, after.st_ctime_ns,
            tuple(segments),
        )
    finally:
        os.close(descriptor)


def read_elf_build_id(path: Path) -> str:
    return _other_dso_snapshot(path, None).build_id


def authenticate_other_dso_snapshot(path: Path, expected_build_id: str) -> OtherDsoSnapshot:
    return _other_dso_snapshot(path, expected_build_id)


def verify_other_dso_snapshot(path: Path, expected: OtherDsoSnapshot) -> OtherDsoSnapshot:
    actual = _other_dso_snapshot(path, expected.build_id)
    require(actual == expected, "other DSO snapshot mismatch")
    return actual


def _validate_other_dso_mmap(
    mapping: MMap2, snapshot: OtherDsoSnapshot, page_size: int,
) -> None:
    require(mapping.union_mode == "build_id" and
            mapping.union_identity == snapshot.build_id.lower(),
            "other DSO MMAP2 authenticated build ID mismatch")
    require(mapping.protection == "r-xp", "other DSO MMAP2 protection mismatch")
    matches = []
    for segment in snapshot.executable_segments:
        require(segment.file_offset % page_size == segment.vaddr % page_size,
                "other DSO executable PT_LOAD page incongruence")
        expected_pgoff = _align_down(segment.file_offset, page_size)
        leading = segment.vaddr - _align_down(segment.vaddr, page_size)
        expected_length = _align_up(leading + segment.file_size, page_size)
        if (mapping.pgoff == expected_pgoff and mapping.length == expected_length and
                mapping.start % page_size == 0 and
                (mapping.start - _align_down(segment.vaddr, page_size)) % page_size == 0):
            matches.append(segment)
    require(len(matches) == 1, "other DSO MMAP2 does not match unique executable PT_LOAD")


def _classify_nonbinary_sample(
    sample: PerfSample, mappings: Sequence[MMap2], build_ids: Mapping[str, str],
    other_dso_snapshots: Mapping[str, OtherDsoSnapshot], page_size: int,
) -> str:
    if sample.dso in KERNEL_DSOS:
        return "kernel"
    if sample.dso in PSEUDO_DSOS:
        return "other_dso"
    require(_canonical_absolute_dso(sample.dso), "unknown or malformed DSO identity")
    expected_build_id = build_ids.get(sample.dso)
    require(expected_build_id is not None, "unknown or malformed DSO identity")
    snapshot = other_dso_snapshots.get(sample.dso)
    require(snapshot is not None and snapshot.path == sample.dso,
            "unknown or malformed DSO identity")
    require(snapshot.build_id == expected_build_id.lower(),
            "other DSO authenticated build ID mismatch")
    applicable = [item for item in mappings
                  if item.dso == sample.dso and item.start <= sample.ip < item.end and
                  "x" in item.protection]
    require(len(applicable) == 1, "unknown or malformed DSO identity")
    mapping = applicable[0]
    require(mapping.union_mode == "build_id" and
            mapping.union_identity == expected_build_id.lower(),
            "unknown or malformed DSO identity")
    _validate_other_dso_mmap(mapping, snapshot, page_size)
    canonical = sample.ip - mapping.start + mapping.pgoff
    require(canonical == sample.dsoff, "nonbinary DSO dsoff mismatch")
    return "other_dso"


def reduce_record(
    rows: Sequence[InstructionRow], segments: Sequence[LoadSegment], perf_script_text: str,
    build_ids: Mapping[str, str], identity: BinaryIdentity, *, page_size: int = 4096,
    simultaneous_records: int = 6,
    other_dso_snapshots: Mapping[str, OtherDsoSnapshot] | None = None,
) -> dict[str, Any]:
    snapshots = dict(other_dso_snapshots or {})
    require(build_ids.get(identity.dso, "").lower() == identity.build_id.lower(), "exact binary build ID mismatch")
    row_by_offset: dict[int, InstructionRow] = {}
    for row in rows:
        require(row.dso == identity.dso, "instruction-map DSO identity mismatch")
        require(row.dso_file_offset not in row_by_offset, f"duplicate canonical DSO offset 0x{row.dso_file_offset:x}")
        row_by_offset[row.dso_file_offset] = row
    mappings, samples = parse_perf_script(perf_script_text)
    for sample in samples:
        if (sample.dso != identity.dso and sample.dso not in KERNEL_DSOS and
                sample.dso not in PSEUDO_DSOS):
            require(_canonical_absolute_dso(sample.dso),
                    "unknown or malformed DSO identity")
    sampled_other_dsos = {
        sample.dso for sample in samples
        if sample.dso != identity.dso and sample.dso not in KERNEL_DSOS and
        sample.dso not in PSEUDO_DSOS
    }
    require(set(snapshots) == sampled_other_dsos,
            "other DSO snapshot cardinality mismatch")
    exact = [item for item in mappings if item.dso == identity.dso]
    require(len(exact) == 1, "expected exactly one executable MMAP2 for exact binary")
    _validate_exact_binary_mmap(exact[0], segments, identity, page_size)
    source_reverse = build_family_reverse_index(rows)
    emitted_reverse = build_emitted_reverse_index(rows)
    special_reverse = {
        "special:kernel": {"classification": "kernel"},
        "special:other_dso": {"classification": "other_dso"},
        "special:binary_unresolved": {"classification": "binary_unresolved"},
    }
    families = {name: empty_aggregate() for name in sorted({item.source_family for item in rows} | set(special_reverse))}
    emitted_families = {name: empty_aggregate() for name in sorted({item.emitted_family for item in rows} | set(special_reverse))}
    binary_periods: list[int] = []
    unresolved_count = 0
    unresolved_period = 0
    for sample in samples:
        if sample.dso == identity.dso:
            candidates = [item for item in exact if item.start <= sample.ip < item.end]
            require(candidates, f"no applicable MMAP2 for exact-binary IP 0x{sample.ip:x}")
            require(len(candidates) == 1, f"multiple applicable MMAP2 mappings for exact-binary IP 0x{sample.ip:x}")
            canonical = sample.ip - candidates[0].start + candidates[0].pgoff
            require(canonical == sample.dsoff, f"dsoff mismatch at exact-binary IP 0x{sample.ip:x}")
            row = row_by_offset.get(canonical)
            require(row is not None, f"unknown exact-binary instruction offset 0x{canonical:x}")
            family = row.source_family
            emitted_family = row.emitted_family
            binary_periods.append(sample.period)
            require(row.resolution_status == "resolved",
                    "sampled unresolved or ambiguous exact-binary instruction")
        else:
            classification = _classify_nonbinary_sample(
                sample, mappings, build_ids, snapshots, page_size,
            )
            family = f"special:{classification}"
            emitted_family = family
        add_period(families[family], sample.period)
        add_period(emitted_families[emitted_family], sample.period)
    count, period, squared = len(samples), sum(item.period for item in samples), sum(item.period ** 2 for item in samples)
    validate_conservation(families, count, period, squared)
    for aggregate in families.values():
        aggregate["share_percent"] = float(aggregate["sum_period"]) * 100.0 / period
    validate_conservation(emitted_families, count, period, squared)
    for aggregate in emitted_families.values():
        aggregate["share_percent"] = float(aggregate["sum_period"]) * 100.0 / period
    binary_sum, binary_squared = sum(binary_periods), sum(item ** 2 for item in binary_periods)
    binary_count = len(binary_periods)
    upper = zero_hit_upper_bound(binary_count, simultaneous_records)
    count_pass = binary_count >= 4787
    bound_pass = upper is not None and upper <= 0.001
    resolution_pass = unresolved_count == 0 and unresolved_period == 0
    return {"schema": "cubr-new24-g5-record-v1", "binary_identity": dataclasses.asdict(identity), "other_dso_snapshots": [dataclasses.asdict(snapshots[path]) for path in sorted(snapshots)], "raw_sample_count": count, "raw_total_period": period, "raw_total_period_squared": squared, "binary_sample_count": binary_count, "binary_sum_period": binary_sum, "binary_sum_period_squared": binary_squared, "binary_zero_hit_upper_bound": upper, "binary_sample_count_gate_pass": count_pass, "binary_zero_hit_bound_gate_pass": bound_pass, "binary_unresolved_sample_count": unresolved_count, "binary_unresolved_sum_period": unresolved_period, "binary_resolution_gate_pass": resolution_pass, "attribution_grade_record_pass": count_pass and bound_pass and resolution_pass, "zero_hit_model": "exact one-sided binomial inversion; alpha=0.05/6; one trial per exact-binary PERF_RECORD_SAMPLE", "simultaneous_records": simultaneous_records, "families": families, "source_families": families, "emitted_families": emitted_families, "family_reverse_index": {"source": source_reverse, "emitted": emitted_reverse, "special": special_reverse}, "symbol_consulted": False, "lost_record_count": 0, "conservation": "PASS"}


def _summarize_dimension(
    first: Mapping[str, Any], second: Mapping[str, Any], *, p5_source_only: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    all_families: dict[str, dict[str, Any]] = {}
    material: dict[str, dict[str, Any]] = {}
    for family in sorted(set(first) | set(second)):
        shares = [float(first.get(family, empty_aggregate())["share_percent"]), float(second.get(family, empty_aggregate())["share_percent"])]
        threshold_met = shares[0] >= 5.0 or shares[1] >= 5.0
        p5_eligible = p5_source_only and family.startswith("sf:")
        is_material = p5_eligible and threshold_met
        delta = abs(shares[0] - shares[1])
        repeatable = is_material and delta <= 1.0 + 1e-12
        mean = sum(shares) / 200.0
        detail = {"record_shares_percent": shares, "delta_percentage_points": delta, "p5_eligible": p5_eligible, "threshold_met_either_record": threshold_met, "material": is_material, "repeatable": repeatable, "perfect_family_amdahl_ceiling": 1.0 / (1.0 - mean) if repeatable and mean < 1.0 else None}
        all_families[family] = detail
        if is_material:
            material[family] = detail
    return all_families, material


def summarize_file(cell: str, record_a: Mapping[str, Any], record_b: Mapping[str, Any]) -> dict[str, Any]:
    require(record_a.get("schema") == record_b.get("schema") == "cubr-new24-g5-record-v1", "record schema mismatch")
    source, material_source = _summarize_dimension(
        record_a["source_families"], record_b["source_families"], p5_source_only=True,
    )
    emitted, material_emitted = _summarize_dimension(
        record_a["emitted_families"], record_b["emitted_families"], p5_source_only=False,
    )
    return {"schema": "cubr-new24-g5-file-family-summary-v1", "cell": clean_field(cell, "cell"), "families": source, "material_families": material_source, "source_families": source, "material_source_families": material_source, "emitted_families": emitted, "material_emitted_families": material_emitted, "cross_file_reduction_performed": False, "material_threshold_percent_either_record": 5.0, "repeatability_delta_max_percentage_points": 1.0}


def read_regular_bytes(path: Path) -> bytes:
    try:
        before = path.lstat()
    except FileNotFoundError as error:
        raise MappingError(f"missing input artifact: {path}") from error
    require(not stat.S_ISLNK(before.st_mode), f"input artifact is a symlink: {path}")
    require(stat.S_ISREG(before.st_mode), f"input artifact is not a regular file: {path}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        require(stat.S_ISREG(opened.st_mode) and (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), f"input artifact identity changed: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read()
        after = os.fstat(descriptor)
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), f"input artifact changed during read: {path}")
        return payload
    finally:
        os.close(descriptor)


def verify_binary_snapshot(path: Path, expected: BinarySnapshot) -> BinarySnapshot:
    try:
        before_path = path.lstat()
    except FileNotFoundError as error:
        raise MappingError(f"missing exact binary: {path}") from error
    require(not stat.S_ISLNK(before_path.st_mode), f"exact binary is a symlink: {path}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), "exact binary is not regular")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                "exact binary changed during snapshot verification")
        actual = BinarySnapshot(digest.hexdigest(), size, after.st_dev, after.st_ino,
                                bool(after.st_mode & 0o111))
        require(actual == expected, "exact binary snapshot mismatch")
        return actual
    finally:
        os.close(descriptor)


def resolve_contained_regular(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    require(relative and not PurePosixPath(relative).is_absolute() and ".." not in parts, f"artifact name contains traversal: {relative}")
    current = root
    root_stat = root.lstat()
    require(stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode), f"unsafe declared root: {root}")
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError as error:
            raise MappingError(f"missing input artifact: {current}") from error
        require(not stat.S_ISLNK(info.st_mode), f"input component is a symlink: {current}")
        require(stat.S_ISREG(info.st_mode) if index == len(parts) - 1 else stat.S_ISDIR(info.st_mode), f"input artifact is not a regular file: {current}")
    return current


def read_text(path: Path) -> str:
    try:
        return read_regular_bytes(path).decode()
    except UnicodeDecodeError as error:
        raise MappingError(f"input artifact is not UTF-8: {path}") from error


def write_new_bytes(path: Path, payload: bytes) -> None:
    parent = path.parent
    info = parent.lstat()
    require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode), f"unsafe output parent: {parent}")
    try:
        target = path.lstat()
    except FileNotFoundError:
        target = None
    if target is not None:
        require(not stat.S_ISLNK(target.st_mode), f"output artifact is a symlink: {path}")
        raise MappingError(f"output artifact already exists: {path}")
    temp = parent / f".{path.name}.{secrets.token_hex(16)}.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.close(descriptor)
        descriptor = -1
        os.link(temp, path, follow_symlinks=False)
        os.unlink(temp)
        dirfd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass
        raise


def validate_relative_artifact_name(name: str) -> str:
    parts = PurePosixPath(name).parts
    require(name not in {"", ".", ".."} and not PurePosixPath(name).is_absolute() and ".." not in parts and len(parts) == 1, f"artifact name contains traversal: {name}")
    return clean_field(name, "artifact name")


def decode_map_gzip(path: Path) -> str:
    try:
        return decompress_single_gzip(read_regular_bytes(path)).decode()
    except UnicodeDecodeError as error:
        raise MappingError("instruction map is not UTF-8") from error


def build_g5_admission_seal(*, binary_build_id: str, binary_sha256: str,
                            instrument_resulting_main: str,
                            map_artifacts: Sequence[Mapping[str, Any]],
                            mapper_sha256: str, mapper_test_sha256: str,
                            mapping_schema_sha256: str, reuse_decision: str,
                            source_tree: str,
                            toolchain: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "binary_build_id": binary_build_id,
        "binary_sha256": binary_sha256,
        "instrument_resulting_main": instrument_resulting_main,
        "map_artifacts": sorted(map_artifacts, key=lambda row: row["path"]),
        "mapper_sha256": mapper_sha256,
        "mapper_test_sha256": mapper_test_sha256,
        "mapping_schema_sha256": mapping_schema_sha256,
        "page_size": 4096,
        "performance_sample": "NO",
        "reuse_decision": reuse_decision,
        "schema": "cubr-new24-g5-map-admission-seal-v1",
        "source_tree": source_tree,
        "toolchain": dict(sorted(toolchain.items())),
    }


def _valid_identity_text(value: Any) -> bool:
    return type(value) is str and bool(value) and not any(
        character in value for character in "\0\t\r\n"
    )


def _valid_toolchain_identity(value: Any) -> bool:
    if not isinstance(value, Mapping) or not value:
        return False
    for key, item in value.items():
        if not _valid_identity_text(key):
            return False
        if type(item) is str:
            if not _valid_identity_text(item):
                return False
        elif type(item) is int:
            if item < 0:
                return False
        elif type(item) is not bool:
            return False
    return True


def _valid_map_artifact_identity(value: Any) -> bool:
    if type(value) is not list or not value:
        return False
    paths: list[str] = []
    for row in value:
        if type(row) is not dict or set(row) != {"bytes", "path", "sha256"}:
            return False
        path = row["path"]
        if not _valid_identity_text(path):
            return False
        pure_path = PurePosixPath(path)
        if (pure_path.is_absolute() or ".." in pure_path.parts or
                pure_path.as_posix() != path or path in {".", ".."}):
            return False
        if type(row["bytes"]) is not int or row["bytes"] <= 0:
            return False
        if type(row["sha256"]) is not str or re.fullmatch(
                r"[0-9a-f]{64}", row["sha256"]
        ) is None:
            return False
        paths.append(path)
    return paths == sorted(paths) and len(paths) == len(set(paths))


def _valid_g5_reuse_identity(identity: Any) -> bool:
    if not isinstance(identity, Mapping):
        return False
    return (
        type(identity.get("mapper_sha256")) is str
        and re.fullmatch(r"[0-9a-f]{64}", identity["mapper_sha256"]) is not None
        and type(identity.get("mapper_test_sha256")) is str
        and re.fullmatch(r"[0-9a-f]{64}", identity["mapper_test_sha256"]) is not None
        and type(identity.get("mapping_schema_sha256")) is str
        and re.fullmatch(r"[0-9a-f]{64}", identity["mapping_schema_sha256"]) is not None
        and type(identity.get("source_tree")) is str
        and re.fullmatch(r"[0-9a-f]{40}", identity["source_tree"]) is not None
        and type(identity.get("binary_sha256")) is str
        and re.fullmatch(r"[0-9a-f]{64}", identity["binary_sha256"]) is not None
        and type(identity.get("binary_build_id")) is str
        and re.fullmatch(r"[0-9a-f]{40}", identity["binary_build_id"]) is not None
        and type(identity.get("page_size")) is int
        and identity["page_size"] == 4096
        and _valid_toolchain_identity(identity.get("toolchain"))
        and _valid_map_artifact_identity(identity.get("map_artifacts"))
    )


def g5_reuse_decision(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> str:
    if not (_valid_g5_reuse_identity(existing) and _valid_g5_reuse_identity(candidate)):
        return "REJECTED_IDENTITY_MISMATCH"
    identity_matches = (
        existing.get("mapper_sha256") == candidate.get("mapper_sha256")
        and existing.get("mapper_test_sha256") == candidate.get("mapper_test_sha256")
        and existing.get("mapping_schema_sha256") == candidate.get("mapping_schema_sha256")
        and existing.get("source_tree") == candidate.get("source_tree")
        and (
            existing.get("binary_sha256"), existing.get("binary_build_id")
        ) == (
            candidate.get("binary_sha256"), candidate.get("binary_build_id")
        )
        and existing.get("toolchain") == candidate.get("toolchain")
        and existing.get("page_size") == candidate.get("page_size")
        and existing.get("map_artifacts") == candidate.get("map_artifacts")
    )
    return "REUSED_IDENTITY_MATCH" if identity_matches else "REJECTED_IDENTITY_MISMATCH"


def json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _declared_root(path: Path, label: str) -> Path:
    require(path.is_absolute(), f"{label} root must be absolute")
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"unsafe {label} root: {path}")
    pending = [path]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                child = Path(entry.path)
                child_info = child.lstat()
                require(not stat.S_ISLNK(child_info.st_mode),
                        f"{label} root contains symlink: {child}")
                require(stat.S_ISREG(child_info.st_mode) or stat.S_ISDIR(child_info.st_mode),
                        f"{label} root contains nonregular node: {child}")
                if stat.S_ISDIR(child_info.st_mode):
                    pending.append(child)
    return path


def _input(root: Path, name: Path) -> Path:
    return resolve_contained_regular(_declared_root(root, "input"), str(name))


def _output(root: Path, name: Path) -> Path:
    output_root = _declared_root(root, "output")
    return output_root / validate_relative_artifact_name(str(name))


def _identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-base-id", required=True)
    parser.add_argument("--instrument-sha256", required=True)


def _roots(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    normalize = commands.add_parser("normalize-elf")
    _roots(normalize)
    normalize.add_argument("--readelf-programs", type=Path, required=True)
    normalize.add_argument("--readelf-sections", type=Path, required=True)
    normalize.add_argument("--binary-sha256", required=True)
    _identity_args(normalize)
    normalize.add_argument("--segments-out", type=Path, required=True)
    normalize.add_argument("--sections-out", type=Path, required=True)
    normalize.add_argument("--summary-out", type=Path, required=True)
    build = commands.add_parser("build-map")
    _roots(build)
    for name in ("segments", "sections", "objdump", "resolver-a", "resolver-b", "prefix-table"):
        build.add_argument(f"--{name}", type=Path, required=True)
    build.add_argument("--binary-dso", required=True)
    build.add_argument("--source-base-id", required=True)
    build.add_argument("--mapping-schema-sha256", required=True)
    build.add_argument("--map-part-prefix", required=True)
    build.add_argument("--map-manifest-out", type=Path, required=True)
    build.add_argument("--max-part-bytes", type=int, default=90_000_000)
    build.add_argument("--summary-out", type=Path, required=True)
    seal = commands.add_parser("seal-admission")
    _roots(seal)
    seal.add_argument("--binary-build-id", required=True)
    seal.add_argument("--binary-sha256", required=True)
    seal.add_argument("--instrument-resulting-main", required=True)
    seal.add_argument("--mapper-sha256", required=True)
    seal.add_argument("--mapper-test-sha256", required=True)
    seal.add_argument("--mapping-schema-sha256", required=True)
    seal.add_argument("--reuse-decision", required=True)
    seal.add_argument("--source-tree", required=True)
    seal.add_argument("--toolchain-json", type=Path, required=True)
    seal.add_argument("--map-manifest", type=Path, required=True)
    seal.add_argument("--map-summary", type=Path, required=True)
    seal.add_argument("--raw-stream-evidence", type=Path, required=True)
    seal.add_argument("--seal-out", type=Path, required=True)
    reduce = commands.add_parser("reduce-record")
    _roots(reduce)
    for name in ("map-manifest", "segments", "perf-script", "build-id-list"):
        reduce.add_argument(f"--{name}", type=Path, required=True)
    reduce.add_argument("--page-size", type=int, required=True)
    reduce.add_argument("--binary-dso", required=True)
    reduce.add_argument("--binary-build-id", required=True)
    reduce.add_argument("--binary-device", required=True)
    reduce.add_argument("--binary-inode", type=int, required=True)
    reduce.add_argument("--binary-path", type=Path, required=True)
    reduce.add_argument("--binary-sha256", required=True)
    reduce.add_argument("--binary-size", type=int, required=True)
    reduce.add_argument("--binary-stat-device", type=int, required=True)
    _identity_args(reduce)
    reduce.add_argument("--record-out", type=Path, required=True)
    summarize = commands.add_parser("summarize-file")
    _roots(summarize)
    summarize.add_argument("--cell", required=True)
    summarize.add_argument("--record-a", type=Path, required=True)
    summarize.add_argument("--record-b", type=Path, required=True)
    summarize.add_argument("--summary-out", type=Path, required=True)
    return parser


def _json_input(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise MappingError(f"invalid JSON artifact: {path}") from error
    require(isinstance(value, dict), f"JSON artifact is not an object: {path}")
    return value


def _artifact_identity(path: Path, relative: PurePosixPath) -> dict[str, Any]:
    payload = read_regular_bytes(path)
    require(len(payload) <= 90_000_000, f"map artifact exceeds 90000000 bytes: {relative}")
    return {
        "bytes": len(payload),
        "path": str(relative),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _g5_map_artifacts(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_path = _input(args.input_root, args.map_manifest)
    manifest = _json_input(manifest_path)
    require(manifest.get("schema") == "cubr-new24-g5-map-parts-v1",
            "map manifest schema mismatch")
    manifest_parent = PurePosixPath(str(args.map_manifest)).parent
    declared_parts = manifest.get("parts")
    require(isinstance(declared_parts, list) and declared_parts,
            "map manifest parts are not a nonempty list")
    artifacts: dict[str, dict[str, Any]] = {}

    def add_artifact(relative: PurePosixPath) -> dict[str, Any]:
        row = _artifact_identity(_input(args.input_root, Path(str(relative))), relative)
        previous = artifacts.setdefault(row["path"], row)
        require(previous == row, f"conflicting map artifact identity: {relative}")
        return row

    add_artifact(PurePosixPath(str(args.map_manifest)))
    for item in declared_parts:
        require(isinstance(item, dict) and isinstance(item.get("path"), str),
                "map manifest part path is invalid")
        relative = manifest_parent / validate_relative_artifact_name(item["path"])
        row = add_artifact(relative)
        require(row["bytes"] == item.get("compressed_bytes") and
                row["sha256"] == item.get("compressed_sha256"),
                "map part compressed identity mismatch")

    summary_relative = PurePosixPath(str(args.map_summary))
    summary_row = add_artifact(summary_relative)
    summary_blob = read_regular_bytes(_input(args.input_root, args.map_summary))
    require(summary_blob[4:8] == b"\0\0\0\0", "map summary gzip mtime mismatch")
    summary_payload = decompress_single_gzip(summary_blob)
    try:
        summary = json.loads(summary_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MappingError("invalid compressed map summary") from error
    require(isinstance(summary, dict) and
            summary.get("schema") == "cubr-new24-g5-static-map-summary-v3",
            "map summary schema mismatch")
    require(summary.get("mapping_schema_sha256") == args.mapping_schema_sha256,
            "map summary mapping schema mismatch")

    evidence_relative = PurePosixPath(str(args.raw_stream_evidence))
    evidence_path = _input(args.input_root, args.raw_stream_evidence)
    add_artifact(evidence_relative)
    try:
        evidence_reader = csv.DictReader(io.StringIO(read_text(evidence_path)), delimiter="\t")
        evidence_rows = list(evidence_reader)
    except csv.Error as error:
        raise MappingError("invalid raw-stream evidence") from error
    expected_fields = [
        "source", "uncompressed_bytes", "uncompressed_sha256", "compressed",
        "compressed_bytes", "compressed_sha256",
    ]
    require(bool(evidence_rows) and evidence_reader.fieldnames == expected_fields,
            "raw-stream evidence schema mismatch")
    summary_evidence_count = 0
    for evidence in evidence_rows:
        compressed_name = validate_relative_artifact_name(evidence["compressed"])
        compressed_relative = evidence_relative.parent / compressed_name
        row = add_artifact(compressed_relative)
        try:
            compressed_bytes = int(evidence["compressed_bytes"])
            uncompressed_bytes = int(evidence["uncompressed_bytes"])
        except ValueError as error:
            raise MappingError("raw-stream evidence byte count is invalid") from error
        require(row["bytes"] == compressed_bytes and
                row["sha256"] == evidence["compressed_sha256"],
                "raw-stream compressed identity mismatch")
        require(re.fullmatch(r"[0-9a-f]{64}", evidence["uncompressed_sha256"]) is not None and
                uncompressed_bytes >= 0,
                "raw-stream uncompressed identity mismatch")
        if compressed_relative == summary_relative:
            summary_evidence_count += 1
            require(summary_row == row and len(summary_payload) == uncompressed_bytes and
                    hashlib.sha256(summary_payload).hexdigest() == evidence["uncompressed_sha256"],
                    "map summary raw-stream identity mismatch")
    require(summary_evidence_count == 1,
            "map summary raw-stream evidence cardinality mismatch")

    toolchain = _json_input(_input(args.input_root, args.toolchain_json))
    require(bool(toolchain) and all(
        isinstance(key, str) and isinstance(value, (str, int, bool))
        for key, value in toolchain.items()
    ), "toolchain identity must contain scalar values")
    return list(artifacts.values()), toolchain


def run_command(args: argparse.Namespace) -> None:
    if hasattr(args, "instrument_sha256"):
        require(re.fullmatch(r"[0-9a-f]{64}", args.instrument_sha256) is not None,
                "invalid instrument SHA-256")
    if hasattr(args, "mapping_schema_sha256"):
        require(re.fullmatch(r"[0-9a-f]{64}", args.mapping_schema_sha256) is not None,
                "invalid mapping schema SHA-256")
    if args.command == "normalize-elf":
        segment_text, section_text = normalize_readelf(
            read_text(_input(args.input_root, args.readelf_programs)),
            read_text(_input(args.input_root, args.readelf_sections)),
            args.binary_sha256,
        )
        parsed_segments, parsed_sections = parse_load_segments(segment_text), parse_executable_sections(section_text)
        write_new_bytes(_output(args.output_root, args.segments_out), segment_text.encode())
        write_new_bytes(_output(args.output_root, args.sections_out), section_text.encode())
        write_new_bytes(_output(args.output_root, args.summary_out), json_bytes({
            "schema": "cubr-new24-g5-normalized-elf-v1",
            "binary_sha256": args.binary_sha256,
            "source_base_identity": args.source_base_id,
            "instrument_sha256": args.instrument_sha256,
            "segment_count": len(parsed_segments),
            "section_count": len(parsed_sections),
            "segments_sha256": hashlib.sha256(segment_text.encode()).hexdigest(),
            "sections_sha256": hashlib.sha256(section_text.encode()).hexdigest(),
        }))
    elif args.command == "build-map":
        rows = build_instruction_rows(
            read_text(_input(args.input_root, args.segments)),
            read_text(_input(args.input_root, args.sections)),
            read_text(_input(args.input_root, args.objdump)),
            read_text(_input(args.input_root, args.resolver_a)),
            read_text(_input(args.input_root, args.resolver_b)),
            read_text(_input(args.input_root, args.prefix_table)), args.binary_dso,
        )
        payload = render_instruction_map(rows).encode()
        parts, manifest = split_instruction_map(
            rows, max_compressed_bytes=args.max_part_bytes,
            part_prefix=args.map_part_prefix,
        )
        require(verify_map_parts(parts, manifest) == payload,
                "independent executable-universe split coverage mismatch")
        manifest_payload = json_bytes(manifest)
        summary = {"schema": "cubr-new24-g5-static-map-summary-v3", "source_base_identity": args.source_base_id, "mapping_schema_sha256": args.mapping_schema_sha256, "binary_dso": args.binary_dso, "instruction_count": len(rows), "canonical_uncompressed_bytes": len(payload), "canonical_uncompressed_sha256": hashlib.sha256(payload).hexdigest(), "part_count": len(parts), "manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(), "family_reverse_index": {"source": build_family_reverse_index(rows), "emitted": build_emitted_reverse_index(rows)}, "raw_symbol_is_sample_join_key": False, "split_reassembly": "PASS", "independent_instruction_universe_coverage": "PASS"}
        for compressed, item in zip(parts, manifest["parts"]):
            write_new_bytes(_output(args.output_root, Path(item["path"])), compressed)
        write_new_bytes(_output(args.output_root, args.map_manifest_out), manifest_payload)
        write_new_bytes(_output(args.output_root, args.summary_out), json_bytes(summary))
    elif args.command == "seal-admission":
        for label in ("binary_sha256", "mapper_sha256", "mapper_test_sha256"):
            require(re.fullmatch(r"[0-9a-f]{64}", getattr(args, label)) is not None,
                    f"invalid {label.replace('_', ' ')}")
        require(re.fullmatch(r"[0-9a-f]+", args.binary_build_id) is not None,
                "invalid binary build ID")
        require(re.fullmatch(r"[0-9a-f]{40}", args.instrument_resulting_main) is not None,
                "invalid instrument resulting-main")
        require(re.fullmatch(r"[0-9a-f]{40}", args.source_tree) is not None,
                "invalid source tree")
        require(args.reuse_decision in {
            "REJECTED_IDENTITY_MISMATCH", "REUSED_IDENTITY_MATCH"
        }, "invalid reuse decision")
        map_artifacts, toolchain = _g5_map_artifacts(args)
        seal = build_g5_admission_seal(
            binary_build_id=args.binary_build_id,
            binary_sha256=args.binary_sha256,
            instrument_resulting_main=args.instrument_resulting_main,
            map_artifacts=map_artifacts,
            mapper_sha256=args.mapper_sha256,
            mapper_test_sha256=args.mapper_test_sha256,
            mapping_schema_sha256=args.mapping_schema_sha256,
            reuse_decision=args.reuse_decision,
            source_tree=args.source_tree,
            toolchain=toolchain,
        )
        write_new_bytes(_output(args.output_root, args.seal_out), json_bytes(seal))
    elif args.command == "reduce-record":
        manifest_path = _input(args.input_root, args.map_manifest)
        manifest = _json_input(manifest_path)
        require(manifest.get("schema") == "cubr-new24-g5-map-parts-v1", "map manifest schema mismatch")
        manifest_parent = PurePosixPath(str(args.map_manifest)).parent
        declared_parts = manifest.get("parts", [])
        require(isinstance(declared_parts, list), "map manifest parts are not a list")
        parts: list[bytes] = []
        for item in declared_parts:
            require(isinstance(item, dict) and isinstance(item.get("path"), str),
                    "map manifest part path is invalid")
            part_basename = validate_relative_artifact_name(item["path"])
            part_relative = manifest_parent / part_basename
            parts.append(read_regular_bytes(_input(args.input_root, Path(str(part_relative)))))
        rows = parse_instruction_map(verify_map_parts(parts, manifest).decode())
        binary_path = _input(args.input_root, args.binary_path)
        snapshot = BinarySnapshot(args.binary_sha256, args.binary_size, args.binary_stat_device, args.binary_inode, True)
        verify_binary_snapshot(binary_path, snapshot)
        perf_text = read_text(_input(args.input_root, args.perf_script))
        build_ids = parse_build_id_list(read_text(_input(args.input_root, args.build_id_list)))
        require(list(path for path in build_ids if path == args.binary_dso) == [args.binary_dso],
                "perf buildid-list exact filename binding mismatch")
        segments = parse_load_segments(read_text(_input(args.input_root, args.segments)))
        _mappings, samples = parse_perf_script(perf_text)
        sampled_other_dsos = sorted({
            sample.dso for sample in samples
            if sample.dso != args.binary_dso and sample.dso not in KERNEL_DSOS and
            sample.dso not in PSEUDO_DSOS
        })
        other_dso_snapshots = {
            dso: authenticate_other_dso_snapshot(Path(dso), build_ids.get(dso, ""))
            for dso in sampled_other_dsos
        }
        result = reduce_record(
            rows, segments, perf_text, build_ids,
            BinaryIdentity(args.binary_dso, args.binary_build_id, args.binary_device, args.binary_inode),
            page_size=args.page_size,
            other_dso_snapshots=other_dso_snapshots,
        )
        verify_binary_snapshot(binary_path, snapshot)
        for dso, other_snapshot in other_dso_snapshots.items():
            verify_other_dso_snapshot(Path(dso), other_snapshot)
        result["source_base_identity"] = args.source_base_id
        result["instrument_sha256"] = args.instrument_sha256
        result["binary_snapshot"] = dataclasses.asdict(snapshot)
        write_new_bytes(_output(args.output_root, args.record_out), json_bytes(result))
    elif args.command == "summarize-file":
        write_new_bytes(_output(args.output_root, args.summary_out), json_bytes(summarize_file(
            args.cell, _json_input(_input(args.input_root, args.record_a)),
            _json_input(_input(args.input_root, args.record_b)),
        )))


def main(argv: Sequence[str] | None = None) -> int:
    try:
        run_command(make_parser().parse_args(argv))
    except (MappingError, OSError) as error:
        print(f"VOID: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
