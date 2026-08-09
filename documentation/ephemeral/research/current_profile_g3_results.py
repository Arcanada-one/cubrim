#!/usr/bin/env python3
"""Fail-closed deterministic reducer for the NEW-24 current-profile G3 run.

The reducer never reads ``perf.data`` itself and never invents attribution.
It verifies the immutable producer outputs, independently recomputes the
registered arithmetic, and emits only per-file results.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


class EvidenceError(RuntimeError):
    """A correctness, identity, schema, or evidence-integrity gate failed."""


CELLS: dict[str, dict[str, Any]] = {
    "dickens/max": {
        "dir": "dickens.max",
        "orig_bytes": 10_192_446,
        "orig_sha256": "b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a",
        "archive_bytes": 2_112_521,
        "archive_sha256": "b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82",
    },
    "xml/max": {
        "dir": "xml.max",
        "orig_bytes": 5_345_280,
        "orig_sha256": "0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c",
        "archive_bytes": 338_244,
        "archive_sha256": "d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37",
    },
    "dickens/web": {
        "dir": "dickens.web",
        "orig_bytes": 10_192_446,
        "orig_sha256": "b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a",
        "archive_bytes": 2_300_603,
        "archive_sha256": "a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341",
    },
}

CURRENT_CODE_COMMIT = "e0e8bdb2c2df924877d9dcf8a1897810683a147a"
G2_CODE_COMMIT = "3a13f486aea51470e2079ba66abb94d99fd782d9"
EXPECTED_UNIT = "cubr-new24-current-profile-g3-20260809.service"
EXPECTED_INVOCATION = "049ef5caefa44ee19dad8b6da03f6a19"
EXPECTED_SYSTEMD_CONTRACT = "Type=exec Restart=no RuntimeMaxSec=4h5m"
EXPECTED_PIN = "0-15"
EXPECTED_THREADS = 4
EXPECTED_MANIFEST_ENTRIES = 206
EXPECTED_RAW_FILES = 208
EXPECTED_BINARY_DSO = "/root/cubr-new24-current-profile-g3-target/release/cubrim"
PERF_SCRIPT_PATHS = tuple(
    f"{directory}/perf{record}.script.txt"
    for directory in ("dickens.max", "xml.max", "dickens.web")
    for record in (1, 2)
)

SEMANTIC_BUCKETS = (
    "state_map_predict",
    "state_map_predict_call",
    "state_map_update",
    "state_map_update_call",
    "sm_div",
    "ctr_predict_stationary",
    "ctr_update_stationary",
    "ctr_next_state",
    "ctr_record_store",
)
TARGET_BUCKETS = SEMANTIC_BUCKETS + ("target_unresolved",)
ALL_SAMPLE_BUCKETS = TARGET_BUCKETS + ("other_user", "kernel", "other_dso")
STATE_MAP_BUCKETS = (
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
REQUIRED_EVENTS = (
    "task-clock",
    "cycles",
    "instructions",
    "branches",
    "branch-misses",
    "cache-references",
    "cache-misses",
    "dTLB-load-misses",
    "page-faults",
    "L1-dcache-loads",
    "L1-dcache-load-misses",
)
TERMINAL_KEYS = {
    "schema", "unit", "invocation_id", "start_utc", "exit_utc",
    "systemd_terminal", "service_type", "restart_policy", "runtime_max",
    "nrestarts", "nrestarts_observation", "load_state_after_gc",
    "active_state_after", "sub_state_after", "final_output",
    "final_output_present", "partial_output_absent", "post_run_orphan_count",
    "raw_file_count", "raw_source_content_digest",
    "raw_destination_content_digest", "raw_source_path_digest",
    "raw_destination_path_digest", "raw_manifest_entries",
    "raw_manifest_exclusions", "raw_manifest_check", "raw_tree_symlinks",
    "raw_tree_writable_entries",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    file_stat = os.fstat(fd)
    if not stat.S_ISREG(file_stat.st_mode):
        os.close(fd)
        raise EvidenceError(f"not a regular file: {path}")
    with os.fdopen(fd, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def enumerate_regular_tree(root: Path, *, label: str) -> list[Path]:
    """Enumerate without following links and reject every unsafe node type."""
    try:
        root_mode = root.lstat().st_mode
    except FileNotFoundError as error:
        raise EvidenceError(f"missing {label} directory: {root}") from error
    require(not stat.S_ISLNK(root_mode) and stat.S_ISDIR(root_mode), f"unsafe {label} directory: {root}")
    regular: list[Path] = []

    def walk(directory: Path) -> None:
        with os.scandir(directory) as entries:
            for entry in entries:
                path = directory / entry.name
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode):
                    raise EvidenceError(f"{label} tree contains a symlink: {path.relative_to(root)}")
                if stat.S_ISREG(mode):
                    regular.append(path)
                elif stat.S_ISDIR(mode):
                    walk(path)
                else:
                    raise EvidenceError(
                        f"{label} tree contains an unsupported filesystem node: {path.relative_to(root)}"
                    )

    walk(root)
    return sorted(regular, key=lambda path: path.relative_to(root).as_posix())


def close(a: float, b: float, tolerance: float = 5e-9) -> bool:
    return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def read_kv(path: Path) -> dict[str, str]:
    require(path.is_file() and not path.is_symlink(), f"missing or unsafe key/value file: {path}")
    result: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        require(raw and "=" in raw, f"malformed key/value line {path}:{number}")
        key, value = raw.split("=", 1)
        require(key and key not in result, f"duplicate key {key!r} in {path}")
        result[key] = value
    return result


def read_metric_tsv(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(reader.fieldnames == ["metric", "value"], f"unexpected metric schema: {path}")
        result: dict[str, str] = {}
        for row in reader:
            metric = row["metric"]
            require(metric not in result, f"duplicate metric {metric!r}: {path}")
            result[metric] = row["value"]
    return result


def tree_identity(root: Path) -> dict[str, Any]:
    files = enumerate_regular_tree(root, label="raw")
    paths = [path.relative_to(root).as_posix() for path in files]
    path_stream = "".join(f"{rel}\n" for rel in paths).encode("utf-8")
    # Matches: find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum
    content_stream = "".join(
        f"{sha256_file(root / rel)}  ./{rel}\n" for rel in paths
    ).encode("utf-8")
    return {
        "file_count": len(paths),
        "content_digest_sha256": hashlib.sha256(content_stream).hexdigest(),
        "path_digest_sha256": hashlib.sha256(path_stream).hexdigest(),
    }


def validate_manifest(root: Path) -> dict[str, Any]:
    regular_files = enumerate_regular_tree(root, label="raw")
    regular_by_name = {path.relative_to(root).as_posix(): path for path in regular_files}
    manifest = root / "SHA256SUMS"
    stamp = root / "TIMING-DONE.STAMP"
    require("SHA256SUMS" in regular_by_name, "raw SHA256SUMS is missing or unsafe")
    require("TIMING-DONE.STAMP" in regular_by_name, "raw TIMING-DONE.STAMP is missing or unsafe")
    entries: dict[str, str] = {}
    listed_order: list[str] = []
    pattern = re.compile(r"^([0-9a-f]{64})  \./(.+)$")
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = pattern.fullmatch(line)
        require(match is not None, f"malformed SHA256SUMS line {number}")
        digest, rel = match.groups()
        parts = Path(rel).parts
        require(rel and not rel.startswith("/") and ".." not in parts, f"unsafe manifest path: {rel}")
        require(rel not in entries, f"duplicate manifest path: {rel}")
        entries[rel] = digest
        listed_order.append(rel)
    require(listed_order == sorted(listed_order), "SHA256SUMS paths are not bytewise sorted")
    actual_paths = sorted(
        rel for rel in regular_by_name
        if rel not in {"SHA256SUMS", "TIMING-DONE.STAMP"}
    )
    require(set(entries) == set(actual_paths), "manifest path set mismatch")
    for rel in actual_paths:
        path = regular_by_name[rel]
        actual = sha256_file(path)
        require(actual == entries[rel], f"checksum mismatch: {rel}")
    return {
        "entries": len(entries),
        "raw_file_count": len(regular_files),
        "manifest_sha256": sha256_file(manifest),
        "completion_marker_sha256": sha256_file(stamp),
    }


def parse_utc(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError(f"malformed terminal {field}: {value}") from error


def validate_terminal_evidence(path: Path, raw: Path, invocation_id: str) -> dict[str, Any]:
    values = read_kv(path)
    require(set(values) == TERMINAL_KEYS, "terminal evidence key set mismatch")
    expected_literals = {
        "schema": "current-profile-g3-terminal-observation-v1",
        "unit": EXPECTED_UNIT,
        "systemd_terminal": "Deactivated successfully",
        "service_type": "exec",
        "restart_policy": "no",
        "runtime_max": "4h5m",
        "nrestarts_observation": "live-start-and-read-only-polling-through-terminal",
        "load_state_after_gc": "not-found",
        "active_state_after": "inactive",
        "sub_state_after": "dead",
        "final_output": "/root/cubr-new24-current-profile-g3-20260809",
        "final_output_present": "true",
        "partial_output_absent": "true",
        "raw_manifest_exclusions": "SHA256SUMS,TIMING-DONE.STAMP",
        "raw_manifest_check": "PASS",
    }
    for key, expected in expected_literals.items():
        require(values[key] == expected, f"terminal {key} mismatch")
    require(values["invocation_id"] == invocation_id, "terminal invocation_id mismatch")
    start = parse_utc(values["start_utc"], "start_utc")
    end = parse_utc(values["exit_utc"], "exit_utc")
    require(start < end, "terminal timestamps are not increasing")
    integer_expected = {
        "nrestarts": 0,
        "post_run_orphan_count": 0,
        "raw_file_count": EXPECTED_RAW_FILES,
        "raw_manifest_entries": EXPECTED_MANIFEST_ENTRIES,
        "raw_tree_symlinks": 0,
        "raw_tree_writable_entries": 0,
    }
    converted: dict[str, int] = {}
    for key, expected in integer_expected.items():
        require(re.fullmatch(r"0|[1-9][0-9]*", values[key]) is not None, f"terminal {key} is not an integer")
        converted[key] = int(values[key])
        require(converted[key] == expected, f"terminal {key} mismatch")
    identity = tree_identity(raw)
    require(identity["file_count"] == converted["raw_file_count"], "terminal raw file count mismatch")
    require(values["raw_destination_content_digest"] == identity["content_digest_sha256"], "raw content digest mismatch")
    require(values["raw_destination_path_digest"] == identity["path_digest_sha256"], "raw path digest mismatch")
    require(values["raw_source_content_digest"] == values["raw_destination_content_digest"], "source/destination content digest mismatch")
    require(values["raw_source_path_digest"] == values["raw_destination_path_digest"], "source/destination path digest mismatch")
    result: dict[str, Any] = dict(values)
    result.update(converted)
    result["duration_seconds"] = int((end - start).total_seconds())
    result["tree_identity_algorithm"] = {
        "content": "sha256(sorted sha256sum lines with ./ paths)",
        "paths": "sha256(sorted relative paths with newline terminators)",
    }
    return result


def validate_map_rows(rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    addresses: set[str] = set()
    join_keys: set[tuple[str, str]] = set()
    owner_count = 0
    assigned_count = 0
    unresolved_count = 0
    for index, row in enumerate(rows, 2):
        address = row.get("object_address", "")
        symbol_offset = row.get("symbol_offset", "")
        dso = row.get("dso", "")
        owner = row.get("target_owner", "")
        bucket = row.get("bucket", "")
        require(re.fullmatch(r"0x[0-9a-f]+", address) is not None, f"malformed object_address at map row {index}")
        require(address not in addresses, f"duplicate object_address: {address}")
        addresses.add(address)
        require(symbol_offset and dso, f"empty DSO/symbol offset at map row {index}")
        join_key = (dso, symbol_offset)
        require(join_key not in join_keys, f"duplicate DSO/symbol_offset: {join_key}")
        join_keys.add(join_key)
        require(owner in {"true", "false"}, f"invalid target_owner at map row {index}")
        require(bucket in TARGET_BUCKETS + ("other_user",), f"invalid instruction-map bucket: {bucket}")
        if owner == "true":
            owner_count += 1
            require(bucket in TARGET_BUCKETS, f"target-owner instruction unassigned at row {index}")
            assigned_count += 1
            if bucket == "target_unresolved":
                unresolved_count += 1
        else:
            require(bucket == "other_user", f"non-owner instruction assigned to target bucket at row {index}")
    return {
        "instructions": len(rows),
        "target_owner_instructions": owner_count,
        "assigned_target_instructions": assigned_count,
        "target_unresolved_instructions": unresolved_count,
    }


def validate_instruction_artifact_manifest(root: Path) -> None:
    path = root / "instruction-artifacts.sha256"
    pattern = re.compile(r"^([0-9a-f]{64})  ([^/].*)$")
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = pattern.fullmatch(line)
        require(match is not None, f"malformed instruction-artifacts line {number}")
        digest, rel = match.groups()
        require(rel not in seen and ".." not in Path(rel).parts, f"unsafe or duplicate instruction artifact: {rel}")
        seen.add(rel)
        require(sha256_file(root / rel) == digest, f"instruction artifact digest mismatch: {rel}")
    require(seen == {
        "binary.objdump.raw.txt", "binary.objdump.demangled.txt",
        "binary.object-addresses.txt", "binary.addr2line.txt",
        "objdump-filter-summary.tsv", "full-disassembly-provenance.txt",
        "instruction-map-coverage.tsv", "instruction-map.tsv",
    }, "instruction artifact manifest path set mismatch")


def validate_instruction_map(root: Path) -> dict[str, Any]:
    path = root / "instruction-map.tsv"
    expected_header = ["object_address", "symbol_offset", "file", "line", "target_owner", "bucket", "dso"]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(reader.fieldnames == expected_header, "instruction-map schema mismatch")
        rows = list(reader)
    summary: dict[str, Any] = validate_map_rows(rows)
    coverage = read_metric_tsv(root / "instruction-map-coverage.tsv")
    expected_counts = {
        "target_owner_instructions": summary["target_owner_instructions"],
        "assigned_target_instructions": summary["assigned_target_instructions"],
        "target_unresolved_instructions": summary["target_unresolved_instructions"],
    }
    for key, expected in expected_counts.items():
        require(coverage.get(key) == str(expected), f"instruction coverage {key} mismatch")
    require(coverage.get("coverage_percent") == "100.000000", "instruction coverage is not exactly 100%")
    require(summary["assigned_target_instructions"] == summary["target_owner_instructions"], "instruction target coverage is incomplete")
    map_sha = sha256_file(path)
    require((root / "instruction-map.sha256").read_text(encoding="utf-8").strip() == map_sha, "instruction-map SHA record mismatch")
    validate_instruction_artifact_manifest(root)
    summary["coverage_percent"] = 100.0
    summary["instruction_map_sha256"] = map_sha
    return summary


def audit_join_key_sets(
    map_keys: set[tuple[str, str]],
    perf_keys: set[tuple[str, str]],
) -> dict[str, Any]:
    """Audit the producer's literal ``(DSO, symbol+offset)`` join namespace.

    This deliberately does not demangle, normalize, use instruction pointers,
    or otherwise repair the producer output. A zero exact-key intersection is
    evidence that the frozen attribution join could not have matched.
    """
    require(map_keys, "instruction map has no exact join keys")
    require(perf_keys, "perf scripts have no exact binary join keys")
    intersection = map_keys & perf_keys
    map_mangled = sum(
        symbol.startswith(("_Z", "_R"))
        for _, symbol in map_keys
    )
    perf_demangled = sum("::" in symbol for _, symbol in perf_keys)
    empty_join = not intersection
    mismatch = empty_join and map_mangled > 0 and perf_demangled > 0
    return {
        "status": "FAIL" if empty_join else "PASS",
        "reason_code": (
            "PERF_MAP_SYMBOL_NAMESPACE_MISMATCH"
            if mismatch
            else "PERF_MAP_EXACT_JOIN_EMPTY"
            if empty_join
            else "EXACT_JOIN_KEY_INTERSECTION_PRESENT"
        ),
        "map_join_key_count": len(map_keys),
        "perf_unique_join_key_count": len(perf_keys),
        "map_mangled_join_key_count": map_mangled,
        "perf_demangled_join_key_count": perf_demangled,
        "exact_join_key_intersection_count": len(intersection),
        "join_contract": "exact (dso, symbol_offset) equality",
        "reattribution_performed": False,
        "limitation": "No demangling, address salvage, normalization, or post-hoc attribution is admissible for the frozen campaign.",
    }


def audit_perf_map_namespace(root: Path) -> dict[str, Any]:
    """Compare raw map keys with exact binary keys from all six perf scripts."""
    map_path = root / "instruction-map.tsv"
    with map_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(
            reader.fieldnames == [
                "object_address", "symbol_offset", "file", "line",
                "target_owner", "bucket", "dso",
            ],
            "instruction-map schema mismatch during namespace audit",
        )
        map_keys = {(row["dso"], row["symbol_offset"]) for row in reader}

    line_pattern = re.compile(
        r"^\s*[0-9]+\s+[0-9a-f]+\s+(.+\+0x[0-9a-f]+)\s+\(([^()]*)\)\s*$"
    )
    perf_keys: set[tuple[str, str]] = set()
    per_file_rows: dict[str, int] = {}
    total_rows = 0
    for rel in PERF_SCRIPT_PATHS:
        path = root / rel
        require(path.is_file() and not path.is_symlink(), f"missing or unsafe perf script: {rel}")
        file_rows = 0
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            match = line_pattern.fullmatch(raw_line)
            if match is None:
                continue
            symbol_offset, dso = match.groups()
            if dso != EXPECTED_BINARY_DSO:
                continue
            perf_keys.add((dso, symbol_offset))
            file_rows += 1
        require(file_rows > 0, f"perf script contains no exact binary samples: {rel}")
        per_file_rows[rel] = file_rows
        total_rows += file_rows

    audit = audit_join_key_sets(map_keys, perf_keys)
    audit.update({
        "perf_record_count": len(PERF_SCRIPT_PATHS),
        "perf_script_paths": list(PERF_SCRIPT_PATHS),
        "perf_exact_binary_sample_rows": total_rows,
        "perf_exact_binary_sample_rows_by_file": per_file_rows,
        "binary_dso": EXPECTED_BINARY_DSO,
    })
    return audit


def cycle_class(first: float, second: float) -> str:
    require(first > 0 and second > 0, "cycles must be positive")
    return "cycle-agreement" if abs(first - second) / max(first, second) <= 0.10 + 1e-15 else "cycle-disagreement"


def g3_class(plain: float, record: float) -> str:
    require(plain > 0 and record > 0, "wall times must be positive")
    return "instrument-clean" if record / plain <= 1.10 + 1e-15 else "instrument-perturbed"


def share_stable(first: float, second: float) -> bool:
    return abs(first - second) * 100.0 <= 1.00 + 1e-12


def classify_candidate_gate(
    *, lost: int, target_count: int, target_period: int, target_period_squared: int,
    unresolved_count: int, unresolved_period: int,
) -> dict[str, Any]:
    require(min(lost, target_count, target_period, target_period_squared, unresolved_count, unresolved_period) >= 0, "negative record diagnostic")
    effective: float | None
    upper: float | None
    if target_period == 0 or target_period_squared == 0:
        require(target_period == 0 and target_period_squared == 0 and target_count == 0, "inconsistent zero target diagnostics")
        effective = None
        upper = None
    else:
        effective = target_period * target_period / target_period_squared
        require(effective > 0, "non-positive effective sample size")
        upper = 1.0 - (0.05 / 6.0) ** (1.0 / effective)
    if unresolved_count > 0 or unresolved_period > 0:
        status = "REFUTED"
    elif lost > 0 or effective is None or effective < 4787 or upper is None or upper > 0.001:
        status = "INDETERMINATE"
    else:
        status = "SUPPORTED"
    return {
        "status": status,
        "effective_sample_size": effective,
        "simultaneous_upper_bound": upper,
    }


def parse_bucket_file(path: Path) -> dict[str, dict[str, Any]]:
    expected_header = ["bucket", "sample_count", "sum_period", "sum_period_squared", "total_period", "share"]
    result: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(reader.fieldnames == expected_header, f"bucket-share schema mismatch: {path}")
        for row in reader:
            bucket = row["bucket"]
            require(bucket in ALL_SAMPLE_BUCKETS and bucket not in result, f"unexpected or duplicate bucket {bucket}: {path}")
            try:
                parsed = {
                    "sample_count": int(row["sample_count"]),
                    "sum_period": int(row["sum_period"]),
                    "sum_period_squared": int(row["sum_period_squared"]),
                    "total_period": int(row["total_period"]),
                    "share_fraction": float(row["share"]),
                }
            except ValueError as error:
                raise EvidenceError(f"non-numeric bucket value: {path}") from error
            require(min(parsed["sample_count"], parsed["sum_period"], parsed["sum_period_squared"]) >= 0, f"negative bucket value: {path}")
            require(parsed["total_period"] > 0, f"non-positive total period: {path}")
            expected_share = parsed["sum_period"] / parsed["total_period"]
            require(close(parsed["share_fraction"], expected_share, 5e-9), f"bucket share arithmetic mismatch: {path}:{bucket}")
            result[bucket] = parsed
    require(set(result) == set(ALL_SAMPLE_BUCKETS), f"bucket path set mismatch: {path}")
    totals = {row["total_period"] for row in result.values()}
    require(len(totals) == 1, f"inconsistent total period: {path}")
    require(sum(row["sum_period"] for row in result.values()) == next(iter(totals)), f"bucket periods do not partition total: {path}")
    require(close(sum(row["share_fraction"] for row in result.values()), 1.0, 2e-8), f"bucket shares do not sum to one: {path}")
    return result


def parse_record_diagnostics(path: Path, buckets: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    values = read_metric_tsv(path)
    require(set(values) == {
        "lost_record_count", "target_sample_count", "target_sum_period",
        "target_sum_period_squared", "target_unresolved_sample_count",
        "target_unresolved_sum_period", "effective_sample_size",
        "simultaneous_upper_bound", "candidate_gate",
    }, f"record diagnostics key set mismatch: {path}")
    try:
        numeric = {key: int(values[key]) for key in (
            "lost_record_count", "target_sample_count", "target_sum_period",
            "target_sum_period_squared", "target_unresolved_sample_count",
            "target_unresolved_sum_period",
        )}
    except ValueError as error:
        raise EvidenceError(f"record diagnostics integer parse failed: {path}") from error
    expected_count = sum(int(buckets[b]["sample_count"]) for b in TARGET_BUCKETS)
    expected_period = sum(int(buckets[b]["sum_period"]) for b in TARGET_BUCKETS)
    expected_squared = sum(int(buckets[b]["sum_period_squared"]) for b in TARGET_BUCKETS)
    require(numeric["target_sample_count"] == expected_count, f"target sample count mismatch: {path}")
    require(numeric["target_sum_period"] == expected_period, f"target period mismatch: {path}")
    require(numeric["target_sum_period_squared"] == expected_squared, f"target squared-period mismatch: {path}")
    unresolved = buckets["target_unresolved"]
    require(numeric["target_unresolved_sample_count"] == unresolved["sample_count"], f"unresolved count mismatch: {path}")
    require(numeric["target_unresolved_sum_period"] == unresolved["sum_period"], f"unresolved period mismatch: {path}")
    gate = classify_candidate_gate(
        lost=numeric["lost_record_count"],
        target_count=numeric["target_sample_count"],
        target_period=numeric["target_sum_period"],
        target_period_squared=numeric["target_sum_period_squared"],
        unresolved_count=numeric["target_unresolved_sample_count"],
        unresolved_period=numeric["target_unresolved_sum_period"],
    )
    for key in ("effective_sample_size", "simultaneous_upper_bound"):
        recorded = values[key]
        computed = gate[key]
        if computed is None:
            require(recorded == "NA", f"expected NA {key}: {path}")
        else:
            require(recorded != "NA" and close(float(recorded), computed, 5e-7), f"{key} mismatch: {path}")
    require(values["candidate_gate"] == gate["status"], f"candidate gate mismatch: {path}")
    return {
        **numeric,
        "effective_sample_size": gate["effective_sample_size"],
        "simultaneous_upper_bound": gate["simultaneous_upper_bound"],
        "candidate_gate": gate["status"],
        "limitation": "Zero observed unresolved samples does not prove the StateMap mechanism was cold.",
    }


def parse_perf_stat(path: Path) -> dict[str, list[dict[str, Any]]]:
    events: dict[str, list[dict[str, Any]]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = [field.strip() for field in raw.split("\t")]
        require(len(fields) >= 3, f"unparseable perf-stat line: {path}: {raw}")
        value_text, event = fields[0], fields[2]
        if value_text == "<not supported>":
            value: int | float | None = None
            status = "unsupported"
        else:
            clean_value = value_text.replace(",", "")
            try:
                value = float(clean_value) if "." in clean_value else int(clean_value)
            except ValueError as error:
                raise EvidenceError(f"unparseable perf-stat counter: {path}: {value_text}") from error
            status = "supported"
        events.setdefault(event, []).append({"status": status, "value": value})
    for event in REQUIRED_EVENTS:
        require(event in events and all(row["status"] == "supported" for row in events[event]), f"required perf event unavailable: {path}:{event}")
    for event in REQUIRED_EVENTS[:-2]:
        require(len(events[event]) == 1, f"unexpected perf event cardinality: {path}:{event}")
    return events


def event_scalar(events: Mapping[str, Sequence[Mapping[str, Any]]], event: str) -> float:
    rows = events[event]
    require(len(rows) == 1 and rows[0]["value"] is not None, f"event is not scalar: {event}")
    return float(rows[0]["value"])


def parse_journal(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise EvidenceError(f"invalid journal JSON line {number}") from error
        require(isinstance(value, dict) and isinstance(value.get("event"), str), f"invalid journal record {number}")
        result.append(value)
    require(result, "empty journal")
    return result


def unique_event(events: Sequence[Mapping[str, Any]], event: str, *, cell: str | None = None, tag: str | None = None, record: int | None = None) -> Mapping[str, Any]:
    matches = [row for row in events if row.get("event") == event and (cell is None or row.get("cell") == cell) and (tag is None or row.get("tag") == tag) and (record is None or row.get("record") == record)]
    require(len(matches) == 1, f"journal event cardinality mismatch: event={event} cell={cell} tag={tag} record={record}")
    return matches[0]


def validate_global_evidence(root: Path, journal: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    provenance = read_kv(root / "PROVENANCE.txt")
    stamp = read_kv(root / "TIMING-DONE.STAMP")
    admission = unique_event(journal, "admission_pass")
    systemd = unique_event(journal, "systemd_contract")
    require(unique_event(journal, "run_start").get("budget_s") == 14400, "journal budget mismatch")
    unique_event(journal, "suites_pass")
    require("test result: ok" in (root / "cargo-test-release.log").read_text(encoding="utf-8"), "release suite result missing")
    scheme_log = (root / "cargo-test-scheme-roundtrip.log").read_text(encoding="utf-8")
    require("test result: ok. 7 passed; 0 failed" in scheme_log, "scheme roundtrip suite result missing")
    unique_event(journal, "feasibility_fixture_pass")
    frozen = unique_event(journal, "instruction_map_frozen")
    run_end = unique_event(journal, "run_end")
    require(not [row for row in journal if row["event"] in {"void", "run_failed"}], "journal contains failure or void event")
    required_provenance = {
        "host": "dev-ai", "topology": "cpu0-31=core0-31;cpu32-63=smt0-31",
        "pin": EXPECTED_PIN, "threads": str(EXPECTED_THREADS),
        "code_commit": CURRENT_CODE_COMMIT, "code_detached": "true",
        "code_clean_except_generated_lock": "true",
        "release_flags": "CARGO_PROFILE_RELEASE_DEBUG=1",
        "systemd_contract": EXPECTED_SYSTEMD_CONTRACT,
        "perf_stat_smoke": "PASS", "perf_record_smoke": "PASS",
        "corpus_manifest_cells": "3/3", "journal_archive_cells": "3/3",
    }
    for key, expected in required_provenance.items():
        require(provenance.get(key) == expected, f"provenance {key} mismatch")
    required_stamp = {
        "code_commit": CURRENT_CODE_COMMIT, "pin": EXPECTED_PIN,
        "systemd": EXPECTED_SYSTEMD_CONTRACT, "invocation_id": EXPECTED_INVOCATION,
        "NRestarts": "0", "profile_status": "VALID-DESCRIPTIVE-PROFILE",
        "selection": "NO-SELECT",
    }
    for key, expected in required_stamp.items():
        require(stamp.get(key) == expected, f"completion marker {key} mismatch")
    require(parse_utc(stamp.get("completed_at", ""), "completed_at") is not None, "completion time missing")
    require(systemd.get("contract") == EXPECTED_SYSTEMD_CONTRACT and systemd.get("unit") == EXPECTED_UNIT, "journal systemd contract mismatch")
    require(systemd.get("invocation_id") == EXPECTED_INVOCATION and systemd.get("NRestarts") == 0, "journal systemd identity mismatch")
    for key in ("runner_sha256", "mapper_sha256", "binary_sha256", "generated_lock_sha256", "code_commit"):
        require(str(admission.get(key)) == provenance.get(key), f"admission/provenance mismatch: {key}")
    require(provenance["runner_sha256"] == sha256_file(root / "current-profile-g3-run.sh"), "captured runner SHA mismatch")
    require(provenance["mapper_sha256"] == sha256_file(root / "current_profile_g3_map.py"), "captured mapper SHA mismatch")
    require(provenance["generated_lock_sha256"] == sha256_file(root / "cargo-generated.lock"), "captured Cargo lock SHA mismatch")
    require(stamp["runner_sha256"] == provenance["runner_sha256"], "stamp runner SHA mismatch")
    require(stamp["mapper_sha256"] == provenance["mapper_sha256"], "stamp mapper SHA mismatch")
    require(stamp["binary_sha256"] == provenance["binary_sha256"], "stamp binary SHA mismatch")
    require(stamp["instruction_map_sha256"] == frozen.get("sha256"), "stamp map SHA mismatch")
    require(run_end.get("profile_status") == stamp["profile_status"] and run_end.get("selection") == stamp["selection"], "run-end verdict mismatch")
    return {"provenance": provenance, "completion": stamp, "admission": dict(admission)}


def validate_archives_and_decodes(root: Path, journal: Sequence[Mapping[str, Any]], cell: str, contract: Mapping[str, Any]) -> None:
    directory = root / str(contract["dir"])
    archive_paths = [directory / "canonical-replay-1.cub", directory / "canonical-replay-2.cub"]
    for path in archive_paths:
        require(path.stat().st_size == contract["archive_bytes"], f"archive size mismatch: {cell}:{path.name}")
        require(sha256_file(path) == contract["archive_sha256"], f"archive SHA mismatch: {cell}:{path.name}")
    require(archive_paths[0].read_bytes() == archive_paths[1].read_bytes(), f"archive replays differ: {cell}")
    for tag in ("plain", "pstat1", "pstat2", "prec1", "prec2"):
        decode = unique_event(journal, "decode_ok", cell=cell, tag=tag)
        require(decode.get("output_sha256") == contract["orig_sha256"], f"decode output SHA mismatch: {cell}:{tag}")
        require(float(decode.get("wall_s", 0)) > 0, f"decode wall time invalid: {cell}:{tag}")
    cell_done = unique_event(journal, "cell_done", cell=cell)
    require(cell_done.get("selection") == "NO-SELECT", f"cell selection mismatch: {cell}")


def parse_stability(path: Path, records: Sequence[Mapping[str, Any]]) -> bool:
    expected: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        rows = list(reader)
    require(rows and rows[0] == ["bucket", "delta_percentage_points"], f"stability schema mismatch: {path}")
    require(rows[-1] == ["classification", "share-stable"], f"stability classification mismatch: {path}")
    for row in rows[1:-1]:
        require(len(row) == 2 and row[0] in TARGET_BUCKETS and row[0] not in expected, f"stability bucket mismatch: {path}")
        expected[row[0]] = float(row[1])
    require(set(expected) == set(TARGET_BUCKETS), f"stability bucket set mismatch: {path}")
    for bucket in TARGET_BUCKETS:
        first = records[0]["buckets"][bucket]["share_fraction"]
        second = records[1]["buckets"][bucket]["share_fraction"]
        delta = abs(first - second) * 100.0
        require(close(expected[bucket], delta, 0.0050001), f"stability delta mismatch: {path}:{bucket}")
        require(share_stable(first, second), f"unstable bucket mislabeled stable: {path}:{bucket}")
    return True


def load_g2_comparator(path: Path) -> dict[str, float]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"G2 result is missing or invalid: {path}") from error
    require(data.get("provenance", {}).get("code_commit") == G2_CODE_COMMIT, "G2 code commit mismatch")
    result: dict[str, float] = {}
    for cell in ("dickens/max", "xml/max"):
        try:
            value = data["cells"][cell]["named_shares"]["cm2_ctr_upd"]
            numeric = float(value)
        except (KeyError, TypeError, ValueError) as error:
            raise EvidenceError(f"G2 cm2_ctr_upd comparator missing or invalid: {cell}") from error
        require(0.0 <= numeric <= 100.0, f"G2 cm2_ctr_upd comparator out of range: {cell}")
        result[cell] = numeric
    require(close(result["dickens/max"], 32.81, 1e-12), "G2 dickens/max comparator drift")
    require(close(result["xml/max"], 29.42, 1e-12), "G2 xml/max comparator drift")
    return result


def evaluate_predictions(cells: Mapping[str, Mapping[str, Any]], g2: Mapping[str, float]) -> dict[str, dict[str, Any]]:
    require(set(cells) == set(CELLS), "prediction cell set mismatch")
    p1_deltas = {cell: abs(float(cells[cell]["whole_update_mean_percent"]) - float(g2[cell])) for cell in ("dickens/max", "xml/max")}
    p1 = "SUPPORTED" if all(delta >= 5.0 - 1e-12 for delta in p1_deltas.values()) else "REFUTED"
    record_statuses = [status for cell in CELLS for status in cells[cell]["record_gate_statuses"]]
    require(len(record_statuses) == 6, "P2 requires exactly six record gates")
    if "REFUTED" in record_statuses:
        p2 = "REFUTED"
    elif all(status == "SUPPORTED" for status in record_statuses):
        p2 = "SUPPORTED"
    else:
        require(all(status in {"SUPPORTED", "INDETERMINATE"} for status in record_statuses), "unknown record gate status")
        p2 = "INDETERMINATE"
    material_cells = [cell for cell in CELLS if float(cells[cell]["state_map_total_mean_percent"]) >= 5.0 - 1e-12]
    p3 = "SUPPORTED" if len(material_cells) >= 2 else "REFUTED"
    p4_delta = abs(float(cells["dickens/max"]["state_map_total_mean_percent"]) - float(cells["dickens/web"]["state_map_total_mean_percent"]))
    p4 = "SUPPORTED" if p4_delta <= 10.0 + 1e-12 else "REFUTED"
    p5 = "SUPPORTED" if all(bool(cells[cell]["repeatable"]) for cell in CELLS) else "REFUTED"
    return {
        "P1": {"status": p1, "g2_cm2_ctr_upd_percent": dict(g2), "whole_update_absolute_deltas_percentage_points": p1_deltas, "threshold_percentage_points": 5.0},
        "P2": {"status": p2, "record_statuses": record_statuses, "limitation": "Zero observed unresolved samples does not prove the StateMap mechanism was cold."},
        "P3": {"status": p3, "material_cells": material_cells, "threshold_percent": 5.0, "minimum_cells": 2, "limitation": "This is the exact observed predicate; P2 uncertainty prevents a cold-mechanism inference."},
        "P4": {"status": p4, "dickens_max_web_delta_percentage_points": p4_delta, "threshold_percentage_points": 10.0},
        "P5": {"status": p5, "requirements": "all target buckets <=1pp; cycles <=10%; both records G3 <=1.10 in every cell"},
    }


def route_verdict(*, correctness_ok: bool, predictions: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    if not correctness_ok:
        return {"profile_status": "VOID", "selection": "NO-SELECT"}
    require(set(predictions) == {"P1", "P2", "P3", "P4", "P5"}, "verdict prediction set mismatch")
    eligible = all(predictions[key]["status"] == "SUPPORTED" for key in ("P2", "P3", "P5"))
    if eligible:
        return {"profile_status": "VALID-CURRENT-PROFILE", "selection": "ELIGIBLE-FOR-SEPARATE-PREREGISTRATION"}
    return {"profile_status": "VALID-DESCRIPTIVE-PROFILE", "selection": "NO-SELECT"}


def analyze_cell(root: Path, journal: Sequence[Mapping[str, Any]], cell: str, contract: Mapping[str, Any]) -> dict[str, Any]:
    validate_archives_and_decodes(root, journal, cell, contract)
    directory = root / str(contract["dir"])
    plain_event = unique_event(journal, "decode_ok", cell=cell, tag="plain")
    plain_wall = float(plain_event["wall_s"])
    records: list[dict[str, Any]] = []
    stat_samples: list[dict[str, Any]] = []
    for index in (1, 2):
        buckets = parse_bucket_file(directory / f"perf{index}.bucket-shares.tsv")
        diagnostics = parse_record_diagnostics(directory / f"perf{index}.record-diagnostics.tsv", buckets)
        record_event = unique_event(journal, "decode_ok", cell=cell, tag=f"prec{index}")
        g3_event = unique_event(journal, "G3", cell=cell, record=index)
        record_wall = float(record_event["wall_s"])
        ratio = record_wall / plain_wall
        classification = g3_class(plain_wall, record_wall)
        require(g3_event.get("classification") == classification, f"journal G3 class mismatch: {cell}:{index}")
        require(close(float(g3_event.get("ratio", -1)), ratio, 6e-6), f"journal G3 ratio mismatch: {cell}:{index}")
        records.append({
            "record": index,
            "wall_seconds": record_wall,
            "plain_wall_seconds": plain_wall,
            "g3_ratio": ratio,
            "g3_class": classification,
            "buckets": buckets,
            "diagnostics": diagnostics,
        })
        events = parse_perf_stat(directory / f"pstat{index}.txt")
        stat_event = unique_event(journal, "decode_ok", cell=cell, tag=f"pstat{index}")
        stat_samples.append({"sample": index, "wall_seconds": float(stat_event["wall_s"]), "events": events})
    cycles = [event_scalar(sample["events"], "cycles") for sample in stat_samples]
    cycle_delta = abs(cycles[0] - cycles[1]) / max(cycles)
    cycle_status = cycle_class(*cycles)
    cycle_event = unique_event(journal, "cycle-agreement", cell=cell)
    require(cycle_status == "cycle-agreement", f"journal cycle event contradicts samples: {cell}")
    require(int(cycle_event.get("cycles1", -1)) == int(cycles[0]) and int(cycle_event.get("cycles2", -1)) == int(cycles[1]), f"journal cycle values mismatch: {cell}")
    require(close(float(cycle_event.get("relative_delta", -1)), cycle_delta, 6e-8), f"journal cycle delta mismatch: {cell}")
    stable = parse_stability(directory / "share-stability.tsv", records)
    bucket_means: dict[str, dict[str, float]] = {}
    for bucket in SEMANTIC_BUCKETS:
        first = records[0]["buckets"][bucket]["share_fraction"]
        second = records[1]["buckets"][bucket]["share_fraction"]
        mean = (first + second) / 2.0
        require(0.0 <= mean < 1.0, f"invalid component mean: {cell}:{bucket}")
        bucket_means[bucket] = {
            "record1_share_percent": first * 100.0,
            "record2_share_percent": second * 100.0,
            "arithmetic_mean_share_percent": mean * 100.0,
            "delta_percentage_points": abs(first - second) * 100.0,
            "perfect_component_amdahl_ceiling": 1.0 / (1.0 - mean),
        }
    state_by_record = [sum(record["buckets"][bucket]["share_fraction"] for bucket in STATE_MAP_BUCKETS) for record in records]
    whole_by_record = [sum(record["buckets"][bucket]["share_fraction"] for bucket in WHOLE_UPDATE_BUCKETS) for record in records]
    repeatable = (
        stable
        and cycle_status == "cycle-agreement"
        and all(record["g3_class"] == "instrument-clean" for record in records)
    )
    cell_done = unique_event(journal, "cell_done", cell=cell)
    require(cell_done.get("cycle_class") == cycle_status and cell_done.get("share_class") == "share-stable", f"cell_done stability mismatch: {cell}")
    for index, record in enumerate(records, 1):
        require(cell_done.get(f"record{index}_class") == record["g3_class"], f"cell_done G3 mismatch: {cell}:{index}")
        require(cell_done.get(f"record{index}_gate") == record["diagnostics"]["candidate_gate"], f"cell_done record gate mismatch: {cell}:{index}")
    bits = int(contract["orig_bytes"]) * 8
    for sample in stat_samples:
        sample["cycles_per_bit"] = event_scalar(sample["events"], "cycles") / bits if repeatable else None
        sample["instructions_per_bit"] = event_scalar(sample["events"], "instructions") / bits
        sample["ipc"] = event_scalar(sample["events"], "instructions") / event_scalar(sample["events"], "cycles")
        sample["cache_misses_per_bit"] = event_scalar(sample["events"], "cache-misses") / bits
        sample["dtlb_misses_per_bit"] = event_scalar(sample["events"], "dTLB-load-misses") / bits
    return {
        "cell": cell,
        "orig_bytes": contract["orig_bytes"],
        "orig_sha256": contract["orig_sha256"],
        "archive_bytes": contract["archive_bytes"],
        "archive_sha256": contract["archive_sha256"],
        "plain_wall_seconds": plain_wall,
        "records": records,
        "stat_samples": stat_samples,
        "cycle_relative_delta": cycle_delta,
        "cycle_class": cycle_status,
        "bucket_means": bucket_means,
        "state_map_total_record_percent": [value * 100.0 for value in state_by_record],
        "state_map_total_mean_percent": sum(state_by_record) * 50.0,
        "state_map_total_perfect_component_amdahl_ceiling": 1.0 / (1.0 - sum(state_by_record) / 2.0),
        "whole_update_record_percent": [value * 100.0 for value in whole_by_record],
        "whole_update_mean_percent": sum(whole_by_record) * 50.0,
        "whole_update_perfect_component_amdahl_ceiling": 1.0 / (1.0 - sum(whole_by_record) / 2.0),
        "record_gate_statuses": [record["diagnostics"]["candidate_gate"] for record in records],
        "repeatable": repeatable,
    }


def not_evaluated_predictions(reason_code: str) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "status": "NOT-EVALUATED",
            "admissible": False,
            "reason_code": reason_code,
            "reason": "The attribution join failed before any target-share predicate could be evaluated.",
        }
        for key in ("P1", "P2", "P3", "P4", "P5")
    }


def analyze(raw: Path, g2_result: Path, terminal_evidence: Path) -> dict[str, Any]:
    raw = raw.absolute()
    manifest = validate_manifest(raw)
    require(manifest["entries"] == EXPECTED_MANIFEST_ENTRIES, "raw manifest entry count mismatch")
    require(manifest["raw_file_count"] == EXPECTED_RAW_FILES, "raw file count mismatch")
    journal = parse_journal(raw / "journal.jsonl")
    require(all(row.get("cell") in CELLS for row in journal if "cell" in row), "journal contains an unexpected cell")
    require(sum(row["event"] == "decode_ok" for row in journal) == 15, "journal decode observation count mismatch")
    require(sum(row["event"] == "G3" for row in journal) == 6, "journal G3 observation count mismatch")
    require(sum(row["event"] == "cell_done" for row in journal) == 3, "journal cell_done count mismatch")
    global_evidence = validate_global_evidence(raw, journal)
    invocation = str(global_evidence["completion"]["invocation_id"])
    terminal = validate_terminal_evidence(terminal_evidence, raw, invocation)
    instruction_map = validate_instruction_map(raw)
    require(instruction_map["instruction_map_sha256"] == global_evidence["completion"]["instruction_map_sha256"], "instruction map/global identity mismatch")
    join_audit = audit_perf_map_namespace(raw)
    require(
        join_audit["status"] == "FAIL"
        and join_audit["reason_code"] == "PERF_MAP_SYMBOL_NAMESPACE_MISMATCH",
        "frozen campaign no longer reproduces the registered namespace mismatch",
    )
    for cell, contract in CELLS.items():
        validate_archives_and_decodes(raw, journal, cell, contract)
    reason_code = str(join_audit["reason_code"])
    predictions = not_evaluated_predictions(reason_code)
    verdict = {
        "profile_status": "VOID",
        "selection": "NO-SELECT",
        "failure_class": "TOOL/PARSING-FAILURE",
        "reason_code": reason_code,
        "reason": "The producer joined mangled map symbols to demangled perf symbols with zero exact key intersection.",
        "producer_completion_claim": global_evidence["completion"]["profile_status"],
        "producer_completion_claim_admissible": False,
    }
    return {
        "schema": "cubr-new24-current-profile-g3-result-v2",
        "verdict": verdict,
        "predictions": predictions,
        "archive_decode_identity": {
            "status": "PASS",
            "cells_checked": list(CELLS),
            "canonical_archive_replays_checked": 6,
            "decode_identity_observations_checked": 15,
            "scope": "identity/correctness only; no attribution or bucket conclusion",
        },
        "provenance": {
            "raw_manifest": manifest,
            "terminal": terminal,
            "instruction_map": instruction_map,
            "join_namespace_audit": join_audit,
            "run": global_evidence,
            "g2_comparator": {
                "status": "NOT-CONSULTED",
                "requested_path": str(g2_result),
                "reason": "The campaign became VOID before comparator evaluation.",
            },
        },
        "publication_limits": {
            "scope": "identity proof and namespace-failure diagnosis only",
            "bucket_conclusions_performed": False,
            "prediction_evaluation_performed": False,
            "sample_reattribution_performed": False,
            "cross_file_reduction_performed": False,
            "throughput_unit_conversion_performed": False,
            "inferred_hardware_stall_share_performed": False,
            "candidate_boundary": "VOID/NO-SELECT; no target-share or operating-point conclusion is admissible.",
        },
    }


def format_number(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.9f}"
    return str(value)


def render_metrics(result: Mapping[str, Any]) -> str:
    columns = [
        "cell", "orig_bytes", "archive_bytes", "plain_wall_s",
        "record1_wall_s", "record1_plain_ratio", "record1_class",
        "record2_wall_s", "record2_plain_ratio", "record2_class",
        "cycles1", "cycles2", "cycle_relative_delta", "cycle_class",
        "cycles1_per_bit", "cycles2_per_bit", "instructions1_per_bit",
        "instructions2_per_bit", "ipc1", "ipc2", "cache_misses1_per_bit",
        "cache_misses2_per_bit", "dtlb_misses1_per_bit", "dtlb_misses2_per_bit",
        "record1_lost", "record2_lost", "record1_target_samples",
        "record2_target_samples", "record1_unresolved_samples",
        "record2_unresolved_samples", "record1_effective_sample_size",
        "record2_effective_sample_size", "record1_upper_bound",
        "record2_upper_bound", "record1_gate", "record2_gate",
        "state_map_total_record1_percent", "state_map_total_record2_percent",
        "state_map_total_mean_percent", "state_map_total_amdahl_ceiling",
        "whole_update_record1_percent", "whole_update_record2_percent",
        "whole_update_mean_percent", "whole_update_amdahl_ceiling",
    ]
    lines = ["\t".join(columns)]
    for cell_name in CELLS:
        cell = result["cells"][cell_name]
        records = cell["records"]
        stats = cell["stat_samples"]
        diagnostics = [record["diagnostics"] for record in records]
        values = [
            cell_name, cell["orig_bytes"], cell["archive_bytes"], cell["plain_wall_seconds"],
            records[0]["wall_seconds"], records[0]["g3_ratio"], records[0]["g3_class"],
            records[1]["wall_seconds"], records[1]["g3_ratio"], records[1]["g3_class"],
            event_scalar(stats[0]["events"], "cycles"), event_scalar(stats[1]["events"], "cycles"),
            cell["cycle_relative_delta"], cell["cycle_class"],
            stats[0]["cycles_per_bit"], stats[1]["cycles_per_bit"],
            stats[0]["instructions_per_bit"], stats[1]["instructions_per_bit"],
            stats[0]["ipc"], stats[1]["ipc"], stats[0]["cache_misses_per_bit"],
            stats[1]["cache_misses_per_bit"], stats[0]["dtlb_misses_per_bit"],
            stats[1]["dtlb_misses_per_bit"], diagnostics[0]["lost_record_count"],
            diagnostics[1]["lost_record_count"], diagnostics[0]["target_sample_count"],
            diagnostics[1]["target_sample_count"], diagnostics[0]["target_unresolved_sample_count"],
            diagnostics[1]["target_unresolved_sample_count"], diagnostics[0]["effective_sample_size"],
            diagnostics[1]["effective_sample_size"], diagnostics[0]["simultaneous_upper_bound"],
            diagnostics[1]["simultaneous_upper_bound"], diagnostics[0]["candidate_gate"],
            diagnostics[1]["candidate_gate"], *cell["state_map_total_record_percent"],
            cell["state_map_total_mean_percent"], cell["state_map_total_perfect_component_amdahl_ceiling"],
            *cell["whole_update_record_percent"], cell["whole_update_mean_percent"],
            cell["whole_update_perfect_component_amdahl_ceiling"],
        ]
        lines.append("\t".join(format_number(value) for value in values))
    return "\n".join(lines) + "\n"


def render_bucket_shares(result: Mapping[str, Any]) -> str:
    columns = ["cell", "bucket", "record1_share_percent", "record2_share_percent", "arithmetic_mean_share_percent", "delta_percentage_points", "perfect_component_amdahl_ceiling"]
    lines = ["\t".join(columns)]
    for cell_name in CELLS:
        means = result["cells"][cell_name]["bucket_means"]
        for bucket in SEMANTIC_BUCKETS:
            row = means[bucket]
            values = [cell_name, bucket, row["record1_share_percent"], row["record2_share_percent"], row["arithmetic_mean_share_percent"], row["delta_percentage_points"], row["perfect_component_amdahl_ceiling"]]
            lines.append("\t".join(format_number(value) for value in values))
    return "\n".join(lines) + "\n"


def render_predictions(result: Mapping[str, Any]) -> str:
    lines = ["prediction\tstatus\tdetail_json"]
    for key in ("P1", "P2", "P3", "P4", "P5"):
        prediction = dict(result["predictions"][key])
        status = prediction.pop("status")
        detail = json.dumps(prediction, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        lines.append(f"{key}\t{status}\t{detail}")
    return "\n".join(lines) + "\n"


def render_join_namespace_audit(result: Mapping[str, Any]) -> str:
    audit = result["provenance"]["join_namespace_audit"]
    lines = ["metric\tvalue"]
    for key in sorted(audit):
        value = audit[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        else:
            rendered = format_number(value)
        require("\t" not in rendered and "\n" not in rendered, f"unsafe join audit value: {key}")
        lines.append(f"{key}\t{rendered}")
    return "\n".join(lines) + "\n"


def rendered_outputs(result: Mapping[str, Any]) -> dict[str, bytes]:
    return {
        "result.json": (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8"),
        "join-namespace-audit.tsv": render_join_namespace_audit(result).encode("utf-8"),
        "predictions.tsv": render_predictions(result).encode("utf-8"),
    }


def validate_output_directory(output_dir: Path, *, create: bool) -> dict[str, Path]:
    try:
        mode = output_dir.lstat().st_mode
    except FileNotFoundError:
        require(create, f"missing output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=False)
        mode = output_dir.lstat().st_mode
    require(not stat.S_ISLNK(mode) and stat.S_ISDIR(mode), f"unsafe output directory: {output_dir}")
    nodes: dict[str, Path] = {}
    with os.scandir(output_dir) as entries:
        for entry in entries:
            path = output_dir / entry.name
            node_mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(node_mode):
                raise EvidenceError(f"analysis output contains a symlink: {entry.name}")
            if not stat.S_ISREG(node_mode):
                raise EvidenceError(f"analysis output contains an unsupported filesystem node: {entry.name}")
            nodes[entry.name] = path
    return nodes


def read_regular_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise EvidenceError(f"cannot safely open regular file: {path}") from error
    mode = os.fstat(fd).st_mode
    if not stat.S_ISREG(mode):
        os.close(fd)
        raise EvidenceError(f"not a regular file: {path}")
    with os.fdopen(fd, "rb") as handle:
        return handle.read()


def atomic_write_bytes(output_dir: Path, name: str, body: bytes) -> None:
    """Write via an exclusive randomized file in the already-validated directory."""
    descriptor = -1
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{name}.", suffix=".tmp", dir=str(output_dir)
        )
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output_dir / name)
        temporary_name = None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def write_outputs(result: Mapping[str, Any], output_dir: Path, *, check: bool = False) -> None:
    existing = validate_output_directory(output_dir, create=not check)
    outputs = rendered_outputs(result)
    terminal_path = output_dir / "terminal-observation.txt"
    require("terminal-observation.txt" in existing, "analysis terminal-observation.txt is missing or unsafe")
    manifested = {**outputs, "terminal-observation.txt": read_regular_bytes(terminal_path)}
    manifest = "".join(f"{hashlib.sha256(body).hexdigest()}  {name}\n" for name, body in sorted(manifested.items())).encode("utf-8")
    outputs["SHA256SUMS"] = manifest
    expected_names = set(outputs) | {"terminal-observation.txt"}
    foreign = set(existing) - expected_names
    require(not foreign, f"unexpected analysis output files: {sorted(foreign)}")
    if check:
        for name, body in outputs.items():
            path = output_dir / name
            require(name in existing and read_regular_bytes(path) == body, f"generated output drift: {name}")
        return
    for name, body in outputs.items():
        atomic_write_bytes(output_dir, name, body)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--g2-result", type=Path, required=True)
    parser.add_argument("--terminal-evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = analyze(args.raw, args.g2_result, args.terminal_evidence)
        write_outputs(result, args.output_dir, check=args.check)
    except (EvidenceError, OSError) as error:
        print(f"VOID: {error}", file=sys.stderr)
        return 2
    print(f"{result['verdict']['profile_status']} / {result['verdict']['selection']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
