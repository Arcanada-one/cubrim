#!/usr/bin/env python3
"""Verify a closed reproduction journal against the frozen expected contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


# The observed mtime encoding difference is exactly 16 bytes per archive. This
# leaves 2x headroom for other timestamp spellings while staying far below any
# real compression change.
#
# It used to be 256, sized to reject a 5,732-byte anomaly on silesia/mr that was
# then unexplained. That anomaly is now explained and eliminated at the source:
# rar's archive size is a function of its compression thread count, and rar 7.00
# picks that from the CPU count visible to it when no -mt flag is given. The
# argv template previously gave none, so every host produced a different archive
# from identical input -- and this verifier would have hard-failed an outside
# reviewer's *correct* run on any box that did not resolve to 16 threads,
# blaming a timestamp for it. rar reads /sys/devices/system/cpu/online rather
# than the affinity mask, so neither taskset nor a container CPU limit contains
# it. archiver_templates.json now pins -mt16, removing the auto-detection path,
# so the only residual variation is the timestamp effect this constant is named
# for.
MTIME_HEADER_SLACK = 32
META_ID = 35
RELEASE_COMMIT = "dfb195ef089db738e51153ad4532fdd583f247bf"
MAX_INPUT_BYTES = 64 * 1024 * 1024


class VerificationError(ValueError):
    """Raised when evidence is incomplete, unexpected, or inconsistent."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bounded_read(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise VerificationError(f"missing or oversized input: {path}")
    return path.read_text()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(_bounded_read(path))
    except json.JSONDecodeError as error:
        raise VerificationError(f"invalid JSON: {path}") from error


def _cell_key(row: dict[str, Any]) -> tuple[str, str, str]:
    key = (row.get("corpus"), row.get("file"), row.get("archiver"))
    if any(not isinstance(value, str) or not value for value in key):
        raise VerificationError(f"invalid cell identity: {key!r}")
    return key


def _scope_matches(scope: str, cell: dict[str, Any]) -> bool:
    if scope == "overall":
        return True
    prefix, separator, value = scope.partition(":")
    if separator != ":" or prefix not in {"corpus", "type"}:
        raise VerificationError(f"unsupported aggregate scope: {scope}")
    return cell[prefix] == value


def verify_run(
    *,
    cells_path: Path,
    aggregates_path: Path,
    journal_path: Path,
    sidecar_path: Path,
    expected_cell_count: int = 240,
    expected_aggregate_count: int = 100,
) -> dict[str, object]:
    sidecar = _load_json(sidecar_path)
    if (
        not isinstance(sidecar, dict)
        or sidecar.get("schema_version") != 1
        or sidecar.get("journal_sha256") != _sha256(journal_path)
    ):
        raise VerificationError("journal sidecar hash mismatch")

    try:
        records = [
            json.loads(line)
            for line in _bounded_read(journal_path).splitlines()
            if line
        ]
    except json.JSONDecodeError as error:
        raise VerificationError("journal contains invalid JSON") from error
    if len(records) < 2 or records[0].get("kind") != "run_meta":
        raise VerificationError("journal does not begin with run_meta")
    if (
        records[0].get("schema_version") != 1
        or records[0].get("meta_id") != META_ID
        or records[0].get("release_commit") != RELEASE_COMMIT
    ):
        raise VerificationError("journal identity mismatch")
    if records[-1].get("kind") != "summary" or records[-1].get("status") != "OK":
        raise VerificationError("journal is partial or lacks a successful summary")

    cells = _load_json(cells_path)
    if not isinstance(cells, list) or len(cells) != expected_cell_count:
        raise VerificationError("expected cell count mismatch")
    expected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for cell in cells:
        if not isinstance(cell, dict):
            raise VerificationError("expected cell must be an object")
        key = _cell_key(cell)
        if key in expected:
            raise VerificationError(f"duplicate expected cell: {key!r}")
        expected[key] = cell

    samples: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        if record.get("kind") != "sample":
            continue
        key = _cell_key(record)
        if key in samples:
            raise VerificationError(f"duplicate sample: {key!r}")
        samples[key] = record
    if set(samples) != set(expected):
        raise VerificationError("journal sample keys do not match expected cells")
    if records[-1].get("sample_count") != expected_cell_count:
        raise VerificationError("summary sample count mismatch")

    # rar stores each source file's modification time and widens that encoding
    # for recent timestamps, so its archive size is a function of corpus mtimes
    # and not of content alone. It is the only one of the ten archivers with
    # that property. Requiring byte equality for it would test how the corpus
    # happened to be copied rather than whether the compression reproduced, so
    # rar is held to the round trip and its byte deltas are reported instead of
    # asserted. The other nine stay byte-exact. Deltas are always surfaced --
    # never silently tolerated -- so a real rar regression is still visible.
    byte_variable = {"rar"}
    reported: list[str] = []

    for key, cell in expected.items():
        sample = samples[key]
        if (
            sample.get("encode_rc"),
            sample.get("decode_rc"),
            sample.get("cmp"),
        ) != (0, 0, 0) or sample.get("round_trip_ok") is not True:
            raise VerificationError(f"round trip failure: {key!r}")
        fields = ("orig", "type") if key[2] in byte_variable else (
            "archive_bytes", "orig", "type"
        )
        for field in fields:
            if sample.get(field) != cell.get(field):
                raise VerificationError(f"{field} mismatch: {key!r}")
        if key[2] in byte_variable:
            delta = int(sample.get("archive_bytes", 0)) - int(cell.get("archive_bytes", 0))
            if abs(delta) > MTIME_HEADER_SLACK:
                raise VerificationError(
                    f"archive_bytes mismatch beyond mtime slack: {key!r} "
                    f"({delta:+d} bytes, limit {MTIME_HEADER_SLACK})"
                )
            if delta:
                reported.append(f"{key[0]}/{key[1]}:{delta:+d}")

    aggregates = _load_json(aggregates_path)
    if not isinstance(aggregates, list) or len(aggregates) != expected_aggregate_count:
        raise VerificationError("expected aggregate count mismatch")
    aggregate_keys: set[tuple[str, str]] = set()
    for aggregate in aggregates:
        if not isinstance(aggregate, dict):
            raise VerificationError("aggregate must be an object")
        scope, archiver = aggregate.get("scope"), aggregate.get("archiver")
        key = (scope, archiver)
        if (
            not isinstance(scope, str)
            or not isinstance(archiver, str)
            or key in aggregate_keys
        ):
            raise VerificationError(f"invalid or duplicate aggregate: {key!r}")
        aggregate_keys.add(key)
        members = [
            cell
            for cell in expected.values()
            if cell["archiver"] == archiver and _scope_matches(scope, cell)
        ]
        if not members:
            raise VerificationError(f"aggregate has no member cells: {key!r}")
        denominator = sum(int(cell["orig"]) for cell in members)
        recomputed = sum(
            int(cell["orig"]) * float(cell["published_ratio"]) for cell in members
        ) / denominator
        ratio = aggregate.get("ratio")
        if (
            isinstance(ratio, bool)
            or not isinstance(ratio, (int, float))
            or not math.isfinite(float(ratio))
            or not math.isclose(recomputed, float(ratio), rel_tol=0.0, abs_tol=1e-15)
        ):
            raise VerificationError(
                f"published aggregate mismatch for {key!r}: "
                f"{recomputed} != {ratio}"
            )

    if reported:
        print(
            f"NOTE: {len(reported)} rar cell(s) differ in archive_bytes "
            f"(mtime-dependent, round trips verified): {' '.join(sorted(reported))}",
            file=sys.stderr,
        )

    return {
        "aggregate_count": len(aggregates),
        "byte_exact_cells": len(expected) - len(reported),
        "cell_count": len(cells),
        "rar_byte_deltas": len(reported),
        "journal_sha256": sidecar["journal_sha256"],
        "meta_id": META_ID,
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--sidecar", type=Path)
    args = parser.parse_args()
    package_root = Path(__file__).resolve().parent
    if args.journal is None or args.sidecar is None:
        parser.error("--journal and --sidecar are required")
    summary = verify_run(
        cells_path=package_root / "expected_cells.json",
        aggregates_path=package_root / "expected_aggregates.json",
        journal_path=args.journal,
        sidecar_path=args.sidecar,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
