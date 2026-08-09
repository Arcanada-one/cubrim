#!/usr/bin/env python3
"""Deterministic object-address and PIE-safe sample mapper for NEW-24 G3."""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import sys
from collections import defaultdict
from decimal import Decimal, localcontext
from typing import Iterable, Sequence


SHARE_DELTA_MAX = Decimal("1.00")
EFFECTIVE_SAMPLE_MIN = Decimal("4787")
SIMULTANEOUS_UPPER_BOUND_MAX = Decimal("0.001")
FIXED_RECORD_COUNT = Decimal("6")

TARGET_BUCKET_LINES = {
    "state_map_predict": range(235, 239),
    "state_map_predict_call": {296},
    "state_map_update": range(240, 249),
    "state_map_update_call": {314},
    "sm_div": range(97, 105),
    "ctr_predict_stationary": set(range(291, 300)) - {296},
    "ctr_update_stationary": range(301, 314),
    "ctr_next_state": {315},
    "ctr_record_store": {316},
}

STATE_MAP_TOTAL_BUCKETS = (
    "state_map_predict",
    "state_map_predict_call",
    "state_map_update",
    "state_map_update_call",
    "sm_div",
)
WHOLE_UPDATE_BUCKETS = (
    "state_map_update",
    "state_map_update_call",
    "sm_div",
    "ctr_update_stationary",
    "ctr_next_state",
    "ctr_record_store",
)

BUCKET_ORDER = (
    "state_map_predict",
    "state_map_predict_call",
    "state_map_update",
    "state_map_update_call",
    "sm_div",
    "ctr_predict_stationary",
    "ctr_update_stationary",
    "ctr_next_state",
    "ctr_record_store",
    "target_unresolved",
    "other_user",
    "kernel",
    "other_dso",
)
TARGET_BUCKETS = (*TARGET_BUCKET_LINES.keys(), "target_unresolved")

SYMBOL_HEADER_RE = re.compile(r"^\s*([0-9A-Fa-f]+) <(.+)>:\s*$")
INSTRUCTION_RE = re.compile(r"^\s*([0-9A-Fa-f]+):\s+(?:[0-9A-Fa-f]{2}(?:\s|$))")
INSTRUCTION_LIKE_RE = re.compile(r"^\s*([^\s:]+):\s+(?:[0-9A-Fa-f]{2}(?:\s|$))")
ADDRESS_RE = re.compile(r"^0x([0-9A-Fa-f]+)$")
FILE_LINE_RE = re.compile(r"^(.*):(\d+)(?:\s+.*)?$")
PERF_SAMPLE_RE = re.compile(
    r"^\s*(\d+)\s+([0-9A-Fa-f]+)\s+(.+?)\s+\((.+)\)\s*$"
)
SYMBOL_OFFSET_RE = re.compile(r"^.+\+0x[0-9A-Fa-f]+$")
LOST_RECORD_RE = re.compile(r"PERF_RECORD_LOST|lost[- ]samples?", re.IGNORECASE)


class MappingError(ValueError):
    """The frozen map or a sample cannot be interpreted without ambiguity."""


@dataclasses.dataclass(frozen=True)
class Frame:
    function: str
    file: str
    line: int


@dataclasses.dataclass(frozen=True)
class Instruction:
    address: int
    symbol: str
    symbol_start: int

    @property
    def symbol_offset(self) -> str:
        return f"{self.symbol}+0x{self.address - self.symbol_start:x}"


@dataclasses.dataclass(frozen=True)
class InstructionRow:
    object_address: int
    symbol_offset: str
    file: str
    line: int
    target_owner: bool
    bucket: str
    dso: str


@dataclasses.dataclass(frozen=True)
class BucketShare:
    bucket: str
    period: int
    total_period: int
    sample_count: int = 0
    sum_period_squared: int = 0

    @property
    def sum_period(self) -> int:
        return self.period


@dataclasses.dataclass(frozen=True)
class ObjdumpBlock:
    start: int
    symbol: str
    lines: tuple[str, ...]


def _is_cm2(frame: Frame) -> bool:
    return pathlib.PurePosixPath(frame.file).name == "cm2.rs"


def _target_candidates(frames: Sequence[Frame]) -> dict[str, Frame]:
    candidates: dict[str, Frame] = {}
    for frame in frames:
        if not _is_cm2(frame):
            continue
        for bucket, lines in TARGET_BUCKET_LINES.items():
            if frame.line in lines:
                previous = candidates.get(bucket)
                if previous is not None and previous != frame:
                    raise MappingError(f"target overlap within {bucket}: {previous} vs {frame}")
                candidates[bucket] = frame
    return candidates


def _select_target(frames: Sequence[Frame], address: int) -> tuple[str, Frame] | None:
    candidates = _target_candidates(frames)
    names = set(candidates)
    if not names:
        return None

    precedence = (
        ("sm_div", {"sm_div", "state_map_update", "state_map_update_call"}),
        (
            "state_map_predict",
            {"state_map_predict", "state_map_predict_call", "ctr_predict_stationary"},
        ),
        (
            "state_map_update",
            {"state_map_update", "state_map_update_call", "ctr_update_stationary"},
        ),
    )
    for winner, allowed in precedence:
        if winner in names:
            if not names <= allowed:
                raise MappingError(
                    f"target overlap at object address 0x{address:x}: {sorted(names)}"
                )
            return winner, candidates[winner]

    if len(names) != 1:
        raise MappingError(f"target overlap at object address 0x{address:x}: {sorted(names)}")
    winner = next(iter(names))
    return winner, candidates[winner]


def _is_target_owner(instruction: Instruction, frames: Sequence[Frame]) -> bool:
    target_names = (
        "cm2::sm_div",
        "cm2::StateMap::p12",
        "cm2::StateMap::upd",
        "cm2::Ctr::predict",
        "cm2::Ctr::upd",
    )
    normalized_frame_functions = (
        frame.function.replace(">::", "::").replace("<", "").replace(">", "")
        for frame in frames
    )
    return (
        bool(_target_candidates(frames))
        or any(
            name in function
            for function in normalized_frame_functions
            for name in target_names
        )
        or any(name in instruction.symbol for name in target_names)
    )


def parse_objdump(text: str) -> list[Instruction]:
    instructions: list[Instruction] = []
    current_symbol: str | None = None
    current_start: int | None = None
    seen: set[int] = set()
    for line_number, raw in enumerate(text.splitlines(), 1):
        header = SYMBOL_HEADER_RE.match(raw)
        if header:
            current_start = int(header.group(1), 16)
            current_symbol = header.group(2)
            continue
        instruction = INSTRUCTION_RE.match(raw)
        if instruction:
            if current_symbol is None or current_start is None:
                raise MappingError(f"instruction before symbol at objdump line {line_number}")
            address = int(instruction.group(1), 16)
            if address < current_start:
                raise MappingError(f"instruction precedes symbol at object address 0x{address:x}")
            if address in seen:
                raise MappingError(f"duplicate object address 0x{address:x}")
            seen.add(address)
            instructions.append(Instruction(address, current_symbol, current_start))
            continue
        malformed = INSTRUCTION_LIKE_RE.match(raw)
        if malformed:
            raise MappingError(
                f"malformed instruction address at objdump line {line_number}: {malformed.group(1)}"
            )
    if not instructions:
        raise MappingError("objdump contains no instructions")
    return instructions


def _objdump_blocks(text: str) -> dict[int, ObjdumpBlock]:
    blocks: dict[int, ObjdumpBlock] = {}
    current_start: int | None = None
    current_symbol: str | None = None
    current_lines: list[str] = []

    def finish() -> None:
        if current_start is None or current_symbol is None:
            return
        if current_start in blocks:
            raise MappingError(f"duplicate objdump symbol start 0x{current_start:x}")
        blocks[current_start] = ObjdumpBlock(
            current_start, current_symbol, tuple(current_lines)
        )

    for raw in text.splitlines():
        header = SYMBOL_HEADER_RE.match(raw)
        if header:
            finish()
            current_start = int(header.group(1), 16)
            current_symbol = header.group(2)
            current_lines = [raw]
        elif current_start is not None:
            current_lines.append(raw)
    finish()
    if not blocks:
        raise MappingError("objdump contains no symbol blocks")
    return blocks


def filter_objdumps(raw_text: str, demangled_text: str) -> tuple[str, str, dict[str, int]]:
    """Keep only CM2 blocks after proving raw/demangled address correlation."""
    raw_instructions = parse_objdump(raw_text)
    demangled_instructions = parse_objdump(demangled_text)
    raw_blocks = _objdump_blocks(raw_text)
    demangled_blocks = _objdump_blocks(demangled_text)

    if set(raw_blocks) != set(demangled_blocks):
        raise MappingError("raw and demangled objdump symbol starts differ")

    raw_addresses: dict[int, set[int]] = defaultdict(set)
    demangled_addresses: dict[int, set[int]] = defaultdict(set)
    for instruction in raw_instructions:
        raw_addresses[instruction.symbol_start].add(instruction.address)
    for instruction in demangled_instructions:
        demangled_addresses[instruction.symbol_start].add(instruction.address)
    for start in sorted(raw_blocks):
        if raw_addresses[start] != demangled_addresses[start]:
            raise MappingError(
                f"raw and demangled instruction addresses differ at symbol 0x{start:x}"
            )

    selected_starts = [
        start
        for start in sorted(demangled_blocks)
        if "cubrim::cm2" in demangled_blocks[start].symbol
    ]
    if not selected_starts:
        raise MappingError("demangled objdump contains no cubrim::cm2 symbols")
    selected_instruction_count = sum(len(raw_addresses[start]) for start in selected_starts)
    if selected_instruction_count == 0:
        raise MappingError("selected cubrim::cm2 symbols contain no instructions")

    def render(blocks: dict[int, ObjdumpBlock]) -> str:
        lines: list[str] = []
        for start in selected_starts:
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend(blocks[start].lines)
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"

    summary = {
        "selected_symbols": len(selected_starts),
        "selected_instructions": selected_instruction_count,
        "full_raw_symbols": len(raw_blocks),
        "full_demangled_symbols": len(demangled_blocks),
        "full_raw_instructions": len(raw_instructions),
        "full_demangled_instructions": len(demangled_instructions),
    }
    return render(raw_blocks), render(demangled_blocks), summary


def render_filter_summary(summary: dict[str, int]) -> str:
    keys = (
        "selected_symbols",
        "selected_instructions",
        "full_raw_symbols",
        "full_demangled_symbols",
        "full_raw_instructions",
        "full_demangled_instructions",
    )
    if set(summary) != set(keys) or any(summary[key] < 0 for key in keys):
        raise MappingError("objdump filter summary is incomplete or invalid")
    return "metric\tvalue\n" + "".join(f"{key}\t{summary[key]}\n" for key in keys)


def parse_addr2line(text: str) -> dict[int, list[Frame]]:
    groups: dict[int, list[Frame]] = {}
    current: int | None = None
    pending_function: str | None = None
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        address_match = ADDRESS_RE.match(line)
        if address_match:
            if pending_function is not None:
                raise MappingError(f"addr2line function lacks location before line {line_number}")
            current = int(address_match.group(1), 16)
            if current in groups:
                raise MappingError(f"duplicate addr2line address 0x{current:x}")
            groups[current] = []
            continue
        if line.startswith("0x"):
            raise MappingError(f"malformed addr2line address at line {line_number}: {line}")
        if current is None:
            raise MappingError(f"addr2line frame before address at line {line_number}")
        if pending_function is None:
            pending_function = line
            continue
        if line == "??: ?".replace(" ", ""):
            groups[current].append(Frame(pending_function, "??", 0))
            pending_function = None
            continue
        unknown_line_match = re.match(r"^(.*):\?$", line)
        if unknown_line_match:
            groups[current].append(Frame(pending_function, unknown_line_match.group(1), 0))
            pending_function = None
            continue
        location_match = FILE_LINE_RE.match(line)
        if not location_match:
            raise MappingError(f"malformed addr2line location at line {line_number}: {line}")
        groups[current].append(
            Frame(pending_function, location_match.group(1), int(location_match.group(2)))
        )
        pending_function = None
    if pending_function is not None:
        raise MappingError("addr2line function lacks final location")
    if not groups:
        raise MappingError("addr2line output contains no addresses")
    return groups


def build_instruction_rows(objdump_text: str, addr2line_text: str, binary_dso: str) -> list[InstructionRow]:
    if not pathlib.PurePosixPath(binary_dso).is_absolute():
        raise MappingError("binary DSO must be an absolute path")
    instructions = parse_objdump(objdump_text)
    decoded = parse_addr2line(addr2line_text)
    instruction_addresses = {instruction.address for instruction in instructions}
    extra = set(decoded) - instruction_addresses
    if extra:
        raise MappingError(f"addr2line contains unknown object address 0x{min(extra):x}")

    rows: list[InstructionRow] = []
    for instruction in sorted(instructions, key=lambda item: item.address):
        frames = decoded.get(instruction.address)
        if frames is None:
            raise MappingError(f"missing addr2line address 0x{instruction.address:x}")
        target_owner = _is_target_owner(instruction, frames)
        selected = _select_target(frames, instruction.address) if target_owner else None
        if selected is None and target_owner:
            unresolved_frame = next(
                (frame for frame in frames if _is_cm2(frame)),
                next((frame for frame in frames if frame.file != "??"), Frame("??", "??", 0)),
            )
            selected = "target_unresolved", unresolved_frame
        if selected is None:
            resolved = next((frame for frame in frames if frame.file != "??"), None)
            if resolved is None:
                resolved = Frame("??", "??", 0)
            selected = "other_user", resolved
        bucket, frame = selected
        rows.append(
            InstructionRow(
                object_address=instruction.address,
                symbol_offset=instruction.symbol_offset,
                file=frame.file,
                line=frame.line,
                target_owner=target_owner,
                bucket=bucket,
                dso=binary_dso,
            )
        )
    return rows


def map_coverage(rows: Sequence[InstructionRow]) -> dict[str, int | str]:
    # Canonical rendering also proves unique addresses and DSO/symbol-offset keys.
    render_instruction_map(rows)
    target_rows = [row for row in rows if row.target_owner]
    target_owner = len(target_rows)
    assigned = sum(row.bucket in TARGET_BUCKETS for row in target_rows)
    if target_owner == 0:
        raise MappingError("instruction map contains no target-owner instructions")
    if assigned != target_owner:
        raise MappingError("target-owner instruction coverage is incomplete")
    if any(not row.target_owner and row.bucket in TARGET_BUCKETS for row in rows):
        raise MappingError("non-owner instruction assigned to a target bucket")
    return {
        "target_owner_instructions": target_owner,
        "assigned_target_instructions": assigned,
        "target_unresolved_instructions": sum(
            row.bucket == "target_unresolved" for row in target_rows
        ),
        "coverage_percent": "100.000000",
    }


def render_map_coverage(coverage: dict[str, int | str]) -> str:
    keys = (
        "target_owner_instructions",
        "assigned_target_instructions",
        "target_unresolved_instructions",
        "coverage_percent",
    )
    if set(coverage) != set(keys):
        raise MappingError("instruction map coverage is incomplete")
    return "metric\tvalue\n" + "".join(f"{key}\t{coverage[key]}\n" for key in keys)


def render_instruction_map(rows: Iterable[InstructionRow]) -> str:
    ordered = sorted(rows, key=lambda row: row.object_address)
    seen_addresses: set[int] = set()
    seen_keys: set[tuple[str, str]] = set()
    output = ["object_address\tsymbol_offset\tfile\tline\ttarget_owner\tbucket\tdso"]
    for row in ordered:
        if row.object_address in seen_addresses:
            raise MappingError(f"duplicate map object address 0x{row.object_address:x}")
        key = (row.dso, row.symbol_offset)
        if key in seen_keys:
            raise MappingError(f"duplicate map DSO/symbol offset: {row.dso} {row.symbol_offset}")
        if "\t" in row.symbol_offset or "\t" in row.file or "\t" in row.dso:
            raise MappingError("map field contains a tab")
        seen_addresses.add(row.object_address)
        seen_keys.add(key)
        output.append(
            f"0x{row.object_address:016x}\t{row.symbol_offset}\t{row.file}\t"
            f"{row.line}\t{'true' if row.target_owner else 'false'}\t{row.bucket}\t{row.dso}"
        )
    return "\n".join(output) + "\n"


def parse_instruction_map(text: str) -> list[InstructionRow]:
    lines = text.splitlines()
    expected_header = "object_address\tsymbol_offset\tfile\tline\ttarget_owner\tbucket\tdso"
    if not lines or lines[0] != expected_header:
        raise MappingError("instruction map header mismatch")
    rows: list[InstructionRow] = []
    for line_number, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        if len(fields) != 7:
            raise MappingError(f"instruction map field count mismatch at line {line_number}")
        address_text, symbol_offset, file_name, source_line, owner_text, bucket, dso = fields
        address_match = ADDRESS_RE.match(address_text)
        if not address_match:
            raise MappingError(f"malformed map object address at line {line_number}")
        if bucket not in BUCKET_ORDER:
            raise MappingError(f"unknown map bucket at line {line_number}: {bucket}")
        if owner_text not in {"true", "false"}:
            raise MappingError(f"malformed target owner at map line {line_number}")
        try:
            parsed_line = int(source_line)
        except ValueError as exc:
            raise MappingError(f"malformed source line at map line {line_number}") from exc
        rows.append(
            InstructionRow(
                int(address_match.group(1), 16),
                symbol_offset,
                file_name,
                parsed_line,
                owner_text == "true",
                bucket,
                dso,
            )
        )
    canonical = render_instruction_map(rows)
    if canonical != text:
        raise MappingError("instruction map is not canonically ordered")
    return rows


def reduce_perf_script_with_diagnostics(
    rows: Sequence[InstructionRow],
    perf_script_text: str,
    binary_dso: str,
    additional_lost_records: int = 0,
) -> tuple[list[BucketShare], dict[str, int | Decimal | str | None]]:
    if additional_lost_records < 0:
        raise MappingError("negative additional lost-record count")
    by_key = {(row.dso, row.symbol_offset): row for row in rows}
    mapped_binary_symbols = {
        row.symbol_offset.rpartition("+0x")[0]
        for row in rows
        if row.dso == binary_dso and "+0x" in row.symbol_offset
    }
    periods: dict[str, int] = defaultdict(int)
    sample_counts: dict[str, int] = defaultdict(int)
    period_squares: dict[str, int] = defaultdict(int)
    total = 0
    sample_count = 0
    lost_record_count = additional_lost_records
    for line_number, raw in enumerate(perf_script_text.splitlines(), 1):
        if not raw.strip():
            continue
        if LOST_RECORD_RE.search(raw):
            lost_record_count += 1
            continue
        match = PERF_SAMPLE_RE.match(raw)
        if not match:
            raise MappingError(f"malformed perf script sample at line {line_number}")
        period = int(match.group(1))
        runtime_ip = match.group(2)
        symbol_offset = match.group(3)
        dso = match.group(4)
        if period <= 0:
            raise MappingError(f"non-positive sample period at line {line_number}")
        if not runtime_ip:
            raise MappingError(f"missing runtime virtual address at line {line_number}")
        if dso == binary_dso:
            if not SYMBOL_OFFSET_RE.match(symbol_offset):
                raise MappingError(
                    f"binary sample lacks symbol+offset at line {line_number}; raw virtual address join forbidden"
                )
            row = by_key.get((dso, symbol_offset))
            if row is None:
                sample_symbol = symbol_offset.rpartition("+0x")[0]
                if sample_symbol in mapped_binary_symbols:
                    raise MappingError(
                        f"unmapped binary sample at line {line_number}: {dso} {symbol_offset}"
                    )
                bucket = "other_user"
            else:
                bucket = row.bucket
        elif dso == "[kernel.kallsyms]":
            bucket = "kernel"
        else:
            bucket = "other_dso"
        periods[bucket] += period
        sample_counts[bucket] += 1
        period_squares[bucket] += period * period
        total += period
        sample_count += 1
    if sample_count == 0 or total <= 0:
        raise MappingError("perf script contains no usable samples")
    shares = [
        BucketShare(
            bucket,
            periods[bucket],
            total,
            sample_counts[bucket],
            period_squares[bucket],
        )
        for bucket in BUCKET_ORDER
    ]
    return shares, record_diagnostics(shares, lost_record_count)


def reduce_perf_script(
    rows: Sequence[InstructionRow], perf_script_text: str, binary_dso: str
) -> list[BucketShare]:
    shares, _diagnostics = reduce_perf_script_with_diagnostics(
        rows, perf_script_text, binary_dso
    )
    return shares


def _sample_count(share: BucketShare) -> int:
    if share.sample_count > 0 or share.period == 0:
        return share.sample_count
    return share.period


def _sum_period_squared(share: BucketShare) -> int:
    if share.sum_period_squared > 0 or share.period == 0:
        return share.sum_period_squared
    return share.period


def render_bucket_shares(shares: Sequence[BucketShare]) -> str:
    validate_period_conservation(shares)
    output = ["bucket\tsample_count\tsum_period\tsum_period_squared\ttotal_period\tshare"]
    seen: set[str] = set()
    for share in shares:
        if share.bucket in seen:
            raise MappingError(f"duplicate bucket reduction: {share.bucket}")
        if share.total_period <= 0 or share.period < 0 or share.period > share.total_period:
            raise MappingError(f"invalid bucket reduction: {share.bucket}")
        seen.add(share.bucket)
        ratio = Decimal(share.period) / Decimal(share.total_period)
        output.append(
            f"{share.bucket}\t{_sample_count(share)}\t{share.period}\t"
            f"{_sum_period_squared(share)}\t{share.total_period}\t{ratio:.9f}"
        )
    return "\n".join(output) + "\n"


def parse_bucket_shares(text: str) -> list[BucketShare]:
    lines = text.splitlines()
    if not lines or lines[0] != (
        "bucket\tsample_count\tsum_period\tsum_period_squared\ttotal_period\tshare"
    ):
        raise MappingError("bucket share header mismatch")
    shares: list[BucketShare] = []
    for line_number, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        if len(fields) != 6:
            raise MappingError(f"bucket share field count mismatch at line {line_number}")
        bucket, count_text, period_text, squared_text, total_text, ratio_text = fields
        if bucket not in BUCKET_ORDER:
            raise MappingError(f"unknown bucket at share line {line_number}: {bucket}")
        try:
            share = BucketShare(
                bucket,
                int(period_text),
                int(total_text),
                int(count_text),
                int(squared_text),
            )
            ratio = Decimal(ratio_text)
        except (ValueError, ArithmeticError) as exc:
            raise MappingError(f"malformed bucket share at line {line_number}") from exc
        expected = Decimal(share.period) / Decimal(share.total_period)
        if ratio != expected.quantize(Decimal("0.000000001")):
            raise MappingError(f"bucket share ratio mismatch at line {line_number}")
        shares.append(share)
    validate_period_conservation(shares)
    if render_bucket_shares(shares) != text:
        raise MappingError("bucket shares are not canonically ordered")
    return shares


def composite_period(shares: Sequence[BucketShare], buckets: Sequence[str]) -> int:
    wanted = set(buckets)
    return sum(share.period for share in shares if share.bucket in wanted)


def validate_period_conservation(shares: Sequence[BucketShare]) -> None:
    if not shares:
        raise MappingError("period conservation requires at least one bucket")
    totals = {share.total_period for share in shares}
    if len(totals) != 1:
        raise MappingError("period conservation failed: inconsistent total periods")
    total = next(iter(totals))
    if total <= 0:
        raise MappingError("period conservation failed: non-positive total")
    buckets = [share.bucket for share in shares]
    if len(buckets) != len(set(buckets)):
        raise MappingError("period conservation failed: duplicate bucket")
    if any(share.period < 0 or share.period > total for share in shares):
        raise MappingError("period conservation failed: invalid bucket period")
    for share in shares:
        count = _sample_count(share)
        squared = _sum_period_squared(share)
        if count < 0 or squared < 0:
            raise MappingError("period conservation failed: negative sample moment")
        if share.period == 0 and (count != 0 or squared != 0):
            raise MappingError("period conservation failed: nonzero moment for zero period")
        if share.period > 0 and (count <= 0 or squared <= 0):
            raise MappingError("period conservation failed: missing sample moment")
    observed = sum(share.period for share in shares)
    if observed != total:
        raise MappingError(
            f"period conservation failed: bucket periods {observed} != total {total}"
        )


def record_diagnostics(
    shares: Sequence[BucketShare], lost_record_count: int
) -> dict[str, int | Decimal | str | None]:
    validate_period_conservation(shares)
    if lost_record_count < 0:
        raise MappingError("negative lost-record count")
    target = [share for share in shares if share.bucket in TARGET_BUCKETS]
    target_sample_count = sum(_sample_count(share) for share in target)
    target_sum_period = sum(share.period for share in target)
    target_sum_period_squared = sum(_sum_period_squared(share) for share in target)
    unresolved = next(
        (share for share in shares if share.bucket == "target_unresolved"),
        BucketShare("target_unresolved", 0, shares[0].total_period),
    )
    effective_sample_size: Decimal | None = None
    simultaneous_upper_bound: Decimal | None = None
    if target_sum_period > 0 and target_sum_period_squared > 0:
        with localcontext() as context:
            context.prec = 50
            effective_sample_size = (
                Decimal(target_sum_period) * Decimal(target_sum_period)
            ) / Decimal(target_sum_period_squared)
            simultaneous_upper_bound = Decimal(1) - (
                Decimal("0.05") / FIXED_RECORD_COUNT
            ) ** (Decimal(1) / effective_sample_size)

    if _sample_count(unresolved) > 0 or unresolved.period > 0:
        candidate_gate = "REFUTED"
    elif (
        lost_record_count > 0
        or effective_sample_size is None
        or simultaneous_upper_bound is None
        or effective_sample_size < EFFECTIVE_SAMPLE_MIN
        or simultaneous_upper_bound > SIMULTANEOUS_UPPER_BOUND_MAX
    ):
        candidate_gate = "INDETERMINATE"
    else:
        candidate_gate = "SUPPORTED"
    return {
        "lost_record_count": lost_record_count,
        "target_sample_count": target_sample_count,
        "target_sum_period": target_sum_period,
        "target_sum_period_squared": target_sum_period_squared,
        "target_unresolved_sample_count": _sample_count(unresolved),
        "target_unresolved_sum_period": unresolved.period,
        "effective_sample_size": effective_sample_size,
        "simultaneous_upper_bound": simultaneous_upper_bound,
        "candidate_gate": candidate_gate,
    }


def render_record_diagnostics(
    diagnostics: dict[str, int | Decimal | str | None]
) -> str:
    keys = (
        "lost_record_count",
        "target_sample_count",
        "target_sum_period",
        "target_sum_period_squared",
        "target_unresolved_sample_count",
        "target_unresolved_sum_period",
        "effective_sample_size",
        "simultaneous_upper_bound",
        "candidate_gate",
    )
    if set(diagnostics) != set(keys):
        raise MappingError("record diagnostics are incomplete")
    output = ["metric\tvalue"]
    for key in keys:
        value = diagnostics[key]
        if isinstance(value, Decimal):
            rendered = f"{value:.12f}"
        elif value is None:
            rendered = "NA"
        else:
            rendered = str(value)
        output.append(f"{key}\t{rendered}")
    return "\n".join(output) + "\n"


def composite_shares(shares: Sequence[BucketShare]) -> dict[str, Decimal]:
    validate_period_conservation(shares)
    total = Decimal(shares[0].total_period)
    return {
        "state_map_total": Decimal(composite_period(shares, STATE_MAP_TOTAL_BUCKETS)) / total,
        "whole_update": Decimal(composite_period(shares, WHOLE_UPDATE_BUCKETS)) / total,
    }


def verify_share_stability(
    first: Sequence[BucketShare],
    second: Sequence[BucketShare],
    max_percentage_points: Decimal = SHARE_DELTA_MAX,
) -> dict[str, Decimal]:
    validate_period_conservation(first)
    validate_period_conservation(second)
    first_periods = {share.bucket: share.period for share in first}
    second_periods = {share.bucket: share.period for share in second}
    first_total = Decimal(first[0].total_period)
    second_total = Decimal(second[0].total_period)
    deltas: dict[str, Decimal] = {}
    for bucket in TARGET_BUCKETS:
        first_share = Decimal(first_periods.get(bucket, 0)) / first_total
        second_share = Decimal(second_periods.get(bucket, 0)) / second_total
        delta = abs(first_share - second_share) * Decimal(100)
        deltas[bucket] = delta
        if delta > max_percentage_points:
            raise MappingError(
                f"share instability for {bucket}: {delta}pp > {max_percentage_points}pp"
            )
    return deltas


def classify_share_stability(
    first: Sequence[BucketShare],
    second: Sequence[BucketShare],
    max_percentage_points: Decimal = SHARE_DELTA_MAX,
) -> tuple[dict[str, Decimal], str]:
    validate_period_conservation(first)
    validate_period_conservation(second)
    first_periods = {share.bucket: share.period for share in first}
    second_periods = {share.bucket: share.period for share in second}
    first_total = Decimal(first[0].total_period)
    second_total = Decimal(second[0].total_period)
    deltas = {
        bucket: abs(
            Decimal(first_periods.get(bucket, 0)) / first_total
            - Decimal(second_periods.get(bucket, 0)) / second_total
        )
        * Decimal(100)
        for bucket in TARGET_BUCKETS
    }
    classification = (
        "share-stable"
        if all(delta <= max_percentage_points for delta in deltas.values())
        else "share-unstable"
    )
    return deltas, classification


def render_share_stability(deltas: dict[str, Decimal], classification: str) -> str:
    if classification not in {"share-stable", "share-unstable"}:
        raise MappingError("invalid share-stability classification")
    output = ["bucket\tdelta_percentage_points"]
    for bucket in TARGET_BUCKETS:
        if bucket not in deltas:
            raise MappingError(f"missing stability bucket: {bucket}")
        output.append(f"{bucket}\t{deltas[bucket]:.2f}")
    output.append(f"classification\t{classification}")
    return "\n".join(output) + "\n"


def _read(path: str) -> str:
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise MappingError(f"cannot read {path}: {exc}") from exc


def _write_new(path: str, content: str) -> None:
    destination = pathlib.Path(path)
    if destination.exists() or destination.is_symlink():
        raise MappingError(f"output already exists: {path}")
    try:
        destination.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise MappingError(f"cannot write {path}: {exc}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    filter_parser = subparsers.add_parser(
        "filter", help="correlate full objdumps and retain compact CM2 blocks"
    )
    filter_parser.add_argument("--raw-full", required=True)
    filter_parser.add_argument("--demangled-full", required=True)
    filter_parser.add_argument("--raw-output", required=True)
    filter_parser.add_argument("--demangled-output", required=True)
    filter_parser.add_argument("--summary-output", required=True)
    build = subparsers.add_parser("build", help="build the frozen instruction map")
    build.add_argument("--objdump", required=True)
    build.add_argument("--addr2line", required=True)
    build.add_argument("--binary-dso", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--coverage-output", required=True)
    reduce_parser = subparsers.add_parser("reduce", help="reduce one perf script sample")
    reduce_parser.add_argument("--map", required=True)
    reduce_parser.add_argument("--perf-script", required=True)
    reduce_parser.add_argument("--perf-script-stderr")
    reduce_parser.add_argument("--binary-dso", required=True)
    reduce_parser.add_argument("--output", required=True)
    reduce_parser.add_argument("--diagnostics-output", required=True)
    compare = subparsers.add_parser("compare", help="enforce two-record target stability")
    compare.add_argument("--first", required=True)
    compare.add_argument("--second", required=True)
    compare.add_argument("--max-percentage-points", required=True)
    compare.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "filter":
            destinations = (
                args.raw_output,
                args.demangled_output,
                args.summary_output,
            )
            for destination in destinations:
                if pathlib.Path(destination).exists() or pathlib.Path(destination).is_symlink():
                    raise MappingError(f"output already exists: {destination}")
            raw, demangled, summary = filter_objdumps(
                _read(args.raw_full), _read(args.demangled_full)
            )
            _write_new(args.raw_output, raw)
            _write_new(args.demangled_output, demangled)
            _write_new(args.summary_output, render_filter_summary(summary))
        elif args.command == "build":
            rows = build_instruction_rows(
                _read(args.objdump), _read(args.addr2line), args.binary_dso
            )
            for destination in (args.output, args.coverage_output):
                if pathlib.Path(destination).exists() or pathlib.Path(destination).is_symlink():
                    raise MappingError(f"output already exists: {destination}")
            _write_new(args.output, render_instruction_map(rows))
            _write_new(args.coverage_output, render_map_coverage(map_coverage(rows)))
        elif args.command == "reduce":
            rows = parse_instruction_map(_read(args.map))
            if any(row.dso != args.binary_dso for row in rows):
                raise MappingError("instruction map DSO does not match --binary-dso")
            additional_lost_records = 0
            if args.perf_script_stderr:
                additional_lost_records = sum(
                    bool(LOST_RECORD_RE.search(line))
                    for line in _read(args.perf_script_stderr).splitlines()
                )
            shares, diagnostics = reduce_perf_script_with_diagnostics(
                rows,
                _read(args.perf_script),
                args.binary_dso,
                additional_lost_records,
            )
            for destination in (args.output, args.diagnostics_output):
                if pathlib.Path(destination).exists() or pathlib.Path(destination).is_symlink():
                    raise MappingError(f"output already exists: {destination}")
            _write_new(args.output, render_bucket_shares(shares))
            _write_new(args.diagnostics_output, render_record_diagnostics(diagnostics))
        elif args.command == "compare":
            try:
                maximum = Decimal(args.max_percentage_points)
            except ArithmeticError as exc:
                raise MappingError("malformed --max-percentage-points") from exc
            if maximum < 0:
                raise MappingError("negative --max-percentage-points")
            deltas, classification = classify_share_stability(
                parse_bucket_shares(_read(args.first)),
                parse_bucket_shares(_read(args.second)),
                maximum,
            )
            _write_new(args.output, render_share_stability(deltas, classification))
        else:  # pragma: no cover - argparse makes this unreachable
            raise MappingError(f"unknown command: {args.command}")
    except MappingError as exc:
        print(f"current_profile_g3_map=FAIL reason={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
