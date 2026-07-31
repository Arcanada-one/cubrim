#!/usr/bin/env python3
"""Freeze exact benchmark cells only from independently measured evidence."""

from __future__ import annotations

import json
import hashlib
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ARCHIVERS = frozenset(
    {
        "cubrim",
        "gzip",
        "bzip2",
        "xz",
        "zstd",
        "brotli",
        "lz4",
        "ppmd",
        "7z",
        "rar",
    }
)
META_ID = 35
RELEASE_COMMIT = "dfb195ef089db738e51153ad4532fdd583f247bf"
PUBLIC_BINARY_SHA256 = "b6c3cd251f7148c1895f5b85d30d06df8252a70afbd649e269f673a19e2a5768"
PUBLISHED_RATIO_TOLERANCE = 1e-4
NONDETERMINISTIC_ARCHIVERS = frozenset({"rar", "7z", "ppmd"})


class FreezeError(ValueError):
    """Raised when source data cannot support an exact private freeze."""


@dataclass(frozen=True)
class Snapshot:
    cells: list[dict[str, Any]]
    aggregates: list[dict[str, Any]]

    def write(self, output_dir: Path) -> tuple[Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = (
            (output_dir / "expected_cells.json", self.cells),
            (output_dir / "expected_aggregates.json", self.aggregates),
        )
        for path, value in outputs:
            if path.exists():
                raise FreezeError(f"refusing to overwrite frozen snapshot: {path}")
            body = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
            path.write_text(body)
            os.chmod(path, 0o444)
        return tuple(path for path, _ in outputs)


def evidence_from_timing_journal(
    journal_path: Path,
    sidecar_path: Path,
    *,
    expected_measurement_count: int = 240,
) -> list[dict[str, Any]]:
    try:
        sidecar = json.loads(sidecar_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise FreezeError("invalid timing sidecar") from error
    journal_sha256 = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    if sidecar.get("journal_sha256") != journal_sha256:
        raise FreezeError("timing journal hash mismatch")
    try:
        records = [
            json.loads(line)
            for line in journal_path.read_text().splitlines()
            if line
        ]
    except json.JSONDecodeError as error:
        raise FreezeError("invalid timing journal JSON") from error
    if not records or records[0].get("kind") != "run_meta":
        raise FreezeError("timing journal lacks run_meta")
    meta = records[0]
    if meta.get("meta_id") != META_ID or meta.get("release_code_sha") != RELEASE_COMMIT:
        raise FreezeError("timing journal identity mismatch")
    tools = meta.get("tools")
    cubrim = tools.get("cubrim") if isinstance(tools, dict) else None
    if not isinstance(cubrim, dict) or cubrim.get("sha256") != PUBLIC_BINARY_SHA256:
        raise FreezeError("timing journal did not use the public release binary")

    measurements = [
        record for record in records if record.get("kind") == "measurement"
    ]
    if len(measurements) != expected_measurement_count:
        raise FreezeError(
            f"expected {expected_measurement_count} timing measurements, "
            f"got {len(measurements)}"
        )
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in measurements:
        identity = _identity(row, "archiver")
        if identity in seen:
            raise FreezeError(f"duplicate timing measurement: {identity!r}")
        seen.add(identity)
        if (
            row.get("compress_status"),
            row.get("decompress_status"),
            row.get("cmp_status"),
            row.get("sample_count"),
            row.get("warmup_count"),
        ) != ("OK", "OK", 0, 3, 1):
            raise FreezeError(f"noncanonical timing measurement: {identity!r}")
        evidence.append(
            {
                "archive_bytes": row.get("archive_bytes"),
                "archiver": identity[2],
                "cmp": 0,
                "corpus": identity[0],
                "decode_rc": 0,
                "encode_rc": 0,
                "file": identity[1],
                "orig": row.get("orig_bytes"),
                "type": row.get("type"),
            }
        )
    return sorted(evidence, key=lambda row: (row["corpus"], row["file"], row["archiver"]))


def _finite_ratio(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FreezeError(f"{label} must be numeric")
    ratio = float(value)
    if not math.isfinite(ratio) or ratio <= 0 or ratio >= 1:
        raise FreezeError(f"{label} must be finite and between zero and one")
    return ratio


def _identity(row: dict[str, Any], archiver_field: str) -> tuple[str, str, str]:
    values = (row.get("corpus"), row.get("file"), row.get(archiver_field))
    if any(not isinstance(value, str) or not value for value in values):
        raise FreezeError(f"invalid cell identity: {values!r}")
    return values


def build_snapshot(
    source: dict[str, Any],
    evidence_rows: Iterable[dict[str, Any]],
    *,
    expected_file_count: int = 24,
    expected_aggregate_count: int = 100,
) -> Snapshot:
    if source.get("meta_count") != 1:
        raise FreezeError("source must contain exactly one benchmark meta row")
    meta = source.get("meta")
    if not isinstance(meta, dict) or meta.get("id") != META_ID:
        raise FreezeError(f"expected meta id {META_ID}")
    code_sha = str(meta.get("code_sha", ""))
    if RELEASE_COMMIT not in code_sha:
        raise FreezeError(f"meta code_sha does not identify {RELEASE_COMMIT}")
    labels = meta.get("archivers")
    if not isinstance(labels, dict) or set(labels) != ARCHIVERS:
        raise FreezeError("meta archiver set is not the canonical ten")

    files = source.get("files")
    if not isinstance(files, list) or len(files) != expected_file_count:
        raise FreezeError(
            f"expected {expected_file_count} source files, got "
            f"{len(files) if isinstance(files, list) else 'non-list'}"
        )

    expected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in files:
        if not isinstance(row, dict):
            raise FreezeError("source file row must be an object")
        if row.get("cubrim_rt") != "OK" or row.get("n_archivers") != len(ARCHIVERS):
            raise FreezeError(f"source file is not canonical: {row!r}")
        original_size = row.get("orig")
        if (
            isinstance(original_size, bool)
            or not isinstance(original_size, int)
            or original_size <= 0
        ):
            raise FreezeError("source orig must be a positive integer")
        ratios = row.get("ratio")
        if not isinstance(ratios, dict) or set(ratios) != ARCHIVERS:
            raise FreezeError("source file ratio map is not the canonical ten")
        for archiver in ARCHIVERS:
            identity = _identity({**row, "archiver": archiver}, "archiver")
            if identity in expected:
                raise FreezeError(f"duplicate source cell: {identity!r}")
            expected[identity] = {
                "archiver": archiver,
                "corpus": identity[0],
                "file": identity[1],
                "orig": original_size,
                "published_ratio": _finite_ratio(
                    ratios[archiver], f"ratio for {identity!r}"
                ),
                "type": row.get("type"),
            }

    evidence: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in evidence_rows:
        if not isinstance(row, dict):
            raise FreezeError("evidence row must be an object")
        identity = _identity(row, "archiver")
        if identity in evidence:
            raise FreezeError(f"duplicate evidence cell: {identity!r}")
        evidence[identity] = row

    if len(evidence) != len(expected):
        raise FreezeError(
            f"evidence cell count {len(evidence)} does not match {len(expected)}"
        )
    if set(evidence) != set(expected):
        missing = sorted(set(expected) - set(evidence))
        unexpected = sorted(set(evidence) - set(expected))
        raise FreezeError(f"evidence key mismatch; missing={missing}, unexpected={unexpected}")

    cells: list[dict[str, Any]] = []
    for identity in sorted(expected):
        source_cell = expected[identity]
        row = evidence[identity]
        for field in ("encode_rc", "decode_rc", "cmp"):
            if row.get(field) != 0:
                raise FreezeError(f"{field} is not zero for {identity!r}")
        if row.get("orig") != source_cell["orig"] or row.get("type") != source_cell["type"]:
            raise FreezeError(f"manifest mismatch for {identity!r}")
        archive_bytes = row.get("archive_bytes")
        if (
            isinstance(archive_bytes, bool)
            or not isinstance(archive_bytes, int)
            or archive_bytes <= 0
        ):
            raise FreezeError(f"archive_bytes must be positive for {identity!r}")
        measured_ratio = archive_bytes / source_cell["orig"]
        published_ratio = source_cell["published_ratio"]
        if identity[2] not in NONDETERMINISTIC_ARCHIVERS:
            if identity[2] == "cubrim":
                if not math.isclose(
                    measured_ratio, published_ratio, rel_tol=0.0, abs_tol=1e-15
                ):
                    raise FreezeError(
                        f"Cubrim ratio mismatch for {identity!r}: "
                        f"{measured_ratio} != {published_ratio}"
                    )
            elif abs(measured_ratio - published_ratio) >= PUBLISHED_RATIO_TOLERANCE:
                raise FreezeError(
                    f"ratio mismatch for {identity!r}: measured={measured_ratio}, "
                    f"published={published_ratio}"
                )
        cells.append(
            {
                **source_cell,
                "archive_bytes": archive_bytes,
                "measured_ratio": measured_ratio,
            }
        )

    aggregates = source.get("aggregates")
    if not isinstance(aggregates, list) or len(aggregates) != expected_aggregate_count:
        raise FreezeError(
            f"expected {expected_aggregate_count} aggregate rows, got "
            f"{len(aggregates) if isinstance(aggregates, list) else 'non-list'}"
        )
    aggregate_keys: set[tuple[str, str]] = set()
    canonical_aggregates: list[dict[str, Any]] = []
    for row in aggregates:
        if not isinstance(row, dict):
            raise FreezeError("aggregate row must be an object")
        scope, archiver = row.get("scope"), row.get("archiver")
        if not isinstance(scope, str) or archiver not in ARCHIVERS:
            raise FreezeError(f"invalid aggregate identity: {(scope, archiver)!r}")
        key = (scope, archiver)
        if key in aggregate_keys:
            raise FreezeError(f"duplicate aggregate: {key!r}")
        aggregate_keys.add(key)
        canonical_aggregates.append(
            {
                "archiver": archiver,
                "ratio": _finite_ratio(row.get("ratio"), f"aggregate {key!r}"),
                "scope": scope,
            }
        )

    return Snapshot(cells=cells, aggregates=sorted(
        canonical_aggregates, key=lambda row: (row["scope"], row["archiver"])
    ))
