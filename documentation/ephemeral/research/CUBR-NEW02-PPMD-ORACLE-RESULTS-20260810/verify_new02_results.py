#!/usr/bin/env python3
"""Build and verify the deterministic NEW-02 characterization package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping, Sequence


PACKAGE_SCHEMA = "new02-ppmd-oracle-results-v1"
SOURCE_SCHEMA = "new02-ppmd-oracle-v1"
SOURCE_BASENAME = "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
SOURCE_FINAL_NAMESPACE = (
    "/home/dev/cubr-new02-canonical-runs/"
    "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
)
SOURCE_CODE_SHA = "708cda945a285526610371d812e4f54725eb6baf"
SOURCE_RUN_ID = "4352d71ee8f4479c17312750d3b08f7095f0fb57737fbf55ac8877b10e0864ba"
SOURCE_INVENTORY_SHA256 = "77b355f6b109acb26eb5606cf1538e2e6628fac3f6ed88b76f99f70a9716ceda"
SOURCE_GRID_SHA256 = "8c5f8d8ba6016f03eded06842d444a6ac06f417e6ae8fd01db9d0e0abef206f4"
SOURCE_PREREG_SHA256 = "fd712e0f0936b2fcce94ff49e1d559852d8e7db7b89ec8affa83263c6e6dd093"
SOURCE_PREREG_GIT_BLOB = "d96df7e3478a6ba52b737ef30dea63d68b0e01ac"
SOURCE_TOP_HASHES = {
    "COMPLETE": "9db58ad5bfa01bfeaff2f46807d0645baa2e002cd1ed930585fcefb2ce177d06",
    "MANIFEST.json": "4a39fb5ec1914ae7e1e296c44b2cec4cf4ecf2afa48af3216a9ec2552f3cb88c",
    "provenance.json": "42caafdbcf13c37e3f7b6f57f62a1923c35c470bf2c22bda04d645b3f1b6fc6b",
    "observations.jsonl": "7622bb1eed1199f98c599cdad588340fcffc3df74b03eef32f37b16c4eabe75c",
}

GENERATED_FILES = (
    "README.md",
    "provenance.json",
    "results.tsv",
    "effects.tsv",
    "summary.json",
)

# Filled only after deterministic construction. These pins make a rehashed
# rewrite fail even when an attacker also rewrites SHA256SUMS.
PINNED_HASHES = {
    "README.md": "740c749f53f552239c1f14e77f19c4dfd7c68b8fd7c857131ca42ae84b200240",
    "provenance.json": "1d3fef5e8dd141939e9e4b94dc9ea13ef73b9840332ec4c2fea618d749530a80",
    "results.tsv": "c9489a378b9e0a246ca3c594b85146e8d57e970214c105e331b7273b8a420c8f",
    "effects.tsv": "529ff0b05eba3155c4a37a0208aaa37cd5c42ce19e9fd37398351595201c6ee0",
    "summary.json": "c163d9a8b191e7e69793c4e0b1ba1c2864cc45981ddf60581240b265a3e59ffc",
}

RESULT_COLUMNS = (
    "schema",
    "status",
    "run_id",
    "code_sha",
    "grid_index",
    "cell",
    "cohort",
    "file",
    "relative_path",
    "excluded_from_broad_claims",
    "input_bytes",
    "input_sha256",
    "order",
    "memory_mib",
    "cpu_set",
    "archive_bytes",
    "archive_sha256",
    "member_method",
    "member_paths",
    "inspection_returncode",
    "encode_returncode",
    "encode_elapsed_seconds",
    "encode_peak_rss_kib",
    "decode_returncode",
    "decode_elapsed_seconds",
    "decode_peak_rss_kib",
    "cmp_returncode",
    "cmp_equal",
    "sha256_equal",
    "round_trip",
    "decoded_bytes",
    "decoded_sha256",
    "encode_time_sha256",
    "decode_time_sha256",
)

EFFECT_COLUMNS = (
    "schema",
    "cohort",
    "file",
    "relative_path",
    "excluded_from_broad_claims",
    "input_bytes",
    "o4_m16_archive_bytes",
    "o4_m64_archive_bytes",
    "o4_m256_archive_bytes",
    "o6_m16_archive_bytes",
    "o6_m64_archive_bytes",
    "o6_m256_archive_bytes",
    "o8_m16_archive_bytes",
    "o8_m64_archive_bytes",
    "o8_m256_archive_bytes",
    "o4_to_o6_at_m16_delta_bytes",
    "o6_to_o8_at_m16_delta_bytes",
    "o4_to_o6_at_m64_delta_bytes",
    "o6_to_o8_at_m64_delta_bytes",
    "o4_to_o6_at_m256_delta_bytes",
    "o6_to_o8_at_m256_delta_bytes",
    "m16_to_m64_at_o4_delta_bytes",
    "m64_to_m256_at_o4_delta_bytes",
    "m16_to_m64_at_o6_delta_bytes",
    "m64_to_m256_at_o6_delta_bytes",
    "m16_to_m64_at_o8_delta_bytes",
    "m64_to_m256_at_o8_delta_bytes",
)


class VerificationError(RuntimeError):
    """A package or source identity failed closed verification."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repository_root() -> Path:
    """Repository root containing this package, resolved from this file."""
    return Path(__file__).resolve().parents[4]


def _historical_validator_path() -> Path:
    return Path(__file__).resolve().with_name("verify_new02_historical.py")


def _load_historical_validator():
    """Load the standalone version-frozen historical validator.

    This deliberately does NOT load the capture harness. The harness
    authenticates provenance with `rev-parse origin/main == code_sha`, a
    capture-time predicate that can never pass again once main advances; the
    historical validator proves the frozen execution commit exists and carries
    its frozen objects instead, which stays true forever.
    """
    path = _historical_validator_path()
    name = "verify_new02_historical_for_result_verification"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise VerificationError("standalone NEW-02 historical validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise VerificationError(
            f"standalone NEW-02 historical validator cannot be loaded: {exc}"
        ) from exc
    return module


def _require_source_top_hashes(raw_root: Path) -> None:
    if raw_root.name != SOURCE_BASENAME or str(raw_root.absolute()) != SOURCE_FINAL_NAMESPACE:
        raise VerificationError("raw publication final namespace mismatch")
    for name, expected in SOURCE_TOP_HASHES.items():
        path = raw_root / name
        if not path.is_file() or sha256_file(path) != expected:
            raise VerificationError(f"raw publication top hash mismatch: {name}")


def _require_no_void_sibling(raw_root: Path) -> None:
    void_entries = sorted(
        path.name for path in raw_root.parent.iterdir() if "void" in path.name.lower()
    )
    if void_entries:
        raise VerificationError(
            "raw publication parent contains a VOID-named record: " + ", ".join(void_entries)
        )


def verify_raw_publication(raw_root: Path) -> Mapping[str, object]:
    """Run the landed authoritative validator against the immutable raw tree."""

    raw_root = raw_root.resolve()
    _require_source_top_hashes(raw_root)
    _require_no_void_sibling(raw_root)
    historical = _load_historical_validator()
    try:
        historical.authenticate_repository(_repository_root())
        marker = historical.validate_raw_publication(raw_root)
    except Exception as exc:
        raise VerificationError(f"historical raw-publication validation failed: {exc}") from exc
    expected = {
        "schema": SOURCE_SCHEMA,
        "status": "COMPLETE",
        "observation_count": 243,
        "manifest_sha256": SOURCE_TOP_HASHES["MANIFEST.json"],
        "final_namespace": SOURCE_FINAL_NAMESPACE,
    }
    if marker != expected:
        raise VerificationError("landed raw-publication completion marker mismatch")
    return marker


def _json_decimal(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line, parse_float=Decimal)
            if not isinstance(value, dict):
                raise VerificationError("source observation is not an object")
            rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, InvalidOperation) as exc:
        raise VerificationError(f"source observations are invalid: {exc}") from exc
    return rows


def _bool_text(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    raise VerificationError("source boolean is not exact")


def _decimal_text(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise VerificationError("source elapsed value is not exact numeric data")
    normalized = Decimal(value)
    if not normalized.is_finite() or normalized < 0:
        raise VerificationError("source elapsed value is not finite and nonnegative")
    return format(normalized, "f")


def _source_to_result_rows(source_rows: Sequence[Mapping[str, object]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for index, row in enumerate(source_rows):
        try:
            inspection = row["archive_inspection"]
            encode = row["encode"]
            decode = row["decode"]
            artifacts = row["artifacts"]
            if not all(isinstance(value, Mapping) for value in (inspection, encode, decode, artifacts)):
                raise VerificationError("source row nested record is invalid")
            relative_path = str(row["relative_path"])
            result = {
                "schema": PACKAGE_SCHEMA,
                "status": "PASS",
                "run_id": str(row["run_id"]),
                "code_sha": str(row["code_sha"]),
                "grid_index": str(index),
                "cell": str(row["cell"]),
                "cohort": str(row["cohort"]),
                "file": str(row["file"]),
                "relative_path": relative_path,
                "excluded_from_broad_claims": _bool_text(relative_path.startswith("canterbury/")),
                "input_bytes": str(row["input_bytes"]),
                "input_sha256": str(row["input_sha256"]),
                "order": str(row["order"]),
                "memory_mib": str(row["memory_mib"]),
                "cpu_set": str(row["cpu_set"]),
                "archive_bytes": str(row["archive_bytes"]),
                "archive_sha256": str(row["archive_sha256"]),
                "member_method": str(inspection["method"]),
                "member_paths": json.dumps(inspection["member_paths"], separators=(",", ":")),
                "inspection_returncode": str(inspection["returncode"]),
                "encode_returncode": str(encode["returncode"]),
                "encode_elapsed_seconds": _decimal_text(encode["elapsed_seconds"]),
                "encode_peak_rss_kib": str(encode["peak_rss_kib"]),
                "decode_returncode": str(decode["returncode"]),
                "decode_elapsed_seconds": _decimal_text(decode["elapsed_seconds"]),
                "decode_peak_rss_kib": str(decode["peak_rss_kib"]),
                "cmp_returncode": str(row["cmp_returncode"]),
                "cmp_equal": _bool_text(row["cmp_equal"]),
                "sha256_equal": _bool_text(row["sha256_equal"]),
                "round_trip": _bool_text(row["round_trip"]),
                "decoded_bytes": str(row["decoded_bytes"]),
                "decoded_sha256": str(row["decoded_sha256"]),
                "encode_time_sha256": str(artifacts["encode_time"]["sha256"]),
                "decode_time_sha256": str(artifacts["decode_time"]["sha256"]),
            }
        except (KeyError, TypeError) as exc:
            raise VerificationError(f"source row {index} is incomplete") from exc
        results.append(result)
    return results


def _effect_rows(result_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in result_rows:
        grouped[(row["cohort"], row["file"], row["relative_path"])].append(row)
    effects: list[dict[str, str]] = []
    for group in grouped.values():
        first = group[0]
        values = {(int(row["order"]), int(row["memory_mib"])): int(row["archive_bytes"]) for row in group}
        if len(group) != 9 or set(values) != {(o, m) for o in (4, 6, 8) for m in (16, 64, 256)}:
            raise VerificationError("source row group is not an exact nine-cell file grid")
        effect = {
            "schema": PACKAGE_SCHEMA,
            "cohort": first["cohort"],
            "file": first["file"],
            "relative_path": first["relative_path"],
            "excluded_from_broad_claims": first["excluded_from_broad_claims"],
            "input_bytes": first["input_bytes"],
        }
        for order in (4, 6, 8):
            for memory in (16, 64, 256):
                effect[f"o{order}_m{memory}_archive_bytes"] = str(values[(order, memory)])
        for memory in (16, 64, 256):
            effect[f"o4_to_o6_at_m{memory}_delta_bytes"] = str(values[(6, memory)] - values[(4, memory)])
            effect[f"o6_to_o8_at_m{memory}_delta_bytes"] = str(values[(8, memory)] - values[(6, memory)])
        for order in (4, 6, 8):
            effect[f"m16_to_m64_at_o{order}_delta_bytes"] = str(values[(order, 64)] - values[(order, 16)])
            effect[f"m64_to_m256_at_o{order}_delta_bytes"] = str(values[(order, 256)] - values[(order, 64)])
        effects.append(effect)
    return effects


def _tsv_bytes(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        if set(row) != set(columns):
            raise VerificationError("generated TSV row has an inexact schema")
        writer.writerow(row)
    return stream.getvalue().encode("utf-8")


def _provenance_document(source: Mapping[str, object]) -> dict[str, object]:
    embedded = source["provenance"]
    if not isinstance(embedded, Mapping):
        raise VerificationError("source provenance is missing")
    return {
        "schema": PACKAGE_SCHEMA,
        "source_publication": {
            "status": "COMPLETE",
            "final_namespace": SOURCE_FINAL_NAMESPACE,
            "observation_count": 243,
            "top_level_sha256": SOURCE_TOP_HASHES,
            "void_record_scope": {
                "scope": str(Path(SOURCE_FINAL_NAMESPACE).parent),
                "status": "NO_VOID_RECORD_PRESENT_IN_SOURCE_PARENT",
            },
        },
        "execution_identity": {
            "exact_main_sha": SOURCE_CODE_SHA,
            "harness_run_id": SOURCE_RUN_ID,
            "systemd_unit": "NOT_RECORDED_BY_CANONICAL_HARNESS",
            "systemd_invocation_id": "NOT_RECORDED_BY_CANONICAL_HARNESS",
            "identity_basis": "harness_run_id",
        },
        "frozen_identities": {
            "inventory_sha256": SOURCE_INVENTORY_SHA256,
            "grid_sha256": SOURCE_GRID_SHA256,
            "preregistration_sha256": SOURCE_PREREG_SHA256,
            "preregistration_git_blob": SOURCE_PREREG_GIT_BLOB,
            "harness_sha256": embedded["harness_sha256"],
            "test_sha256": embedded["test_sha256"],
        },
        "environment": embedded["environment"],
        "tools": embedded["tools"],
        "publication_contract": source["publication"],
        "cpu_set": source["cpu_set"],
        "orders": source["orders"],
        "memory_mib": source["memory_mib"],
    }


def _summary_document() -> dict[str, object]:
    return {
        "schema": PACKAGE_SCHEMA,
        # The five independent status layers the plan defines. They are kept
        # separate on purpose: a later layer must never be able to launder an
        # earlier one. In particular a PASS here authenticates *stored* claims;
        # it never asserts that this validator re-ran 7-Zip or reproduced a
        # measurement, and it never upgrades NO-SELECT into a selection.
        "status_layers": {
            "CAPTURE_STATUS": "COMPLETE",
            "HISTORICAL_VALIDATION_STATUS": "PASS",
            "SCIENTIFIC_CHARACTERIZATION": "CHARACTERIZED_NO_SELECT",
            "PRODUCT_SELECTION_STATUS": "NOT_ISSUED",
            # No supplemental systemd snapshot was ever captured, so the
            # correlated state is unavailable rather than absent-and-ignored.
            # Absence is recorded as absence, never as N/A or PASS.
            "SYSTEMD_CORRELATION_STATUS": "SYSTEMD_EVIDENCE_UNAVAILABLE",
        },
        "verdict": {
            "outcome": "CHARACTERIZED_NO_SELECT",
            "source_status": "COMPLETE",
            "evidence_validation": "PASS",
            "selection": "NO-SELECT",
            "go_no_go": "NOT_ISSUED",
            "candidate": "NONE",
            "ceiling": "NOT_DEFINED_IN_PREREGISTRATION",
            "fraction_of_ceiling": "NOT_COMPUTED",
            "reason": (
                "The prospective preregistration froze measurement mechanics but no "
                "ceiling, aggregate, ranking, winner rule, or implementation-selection rule."
            ),
        },
        "scope": {
            "inventory_entries": 27,
            "observation_cells": 243,
            "per_file_only": True,
            "corpus_wide_average": "NOT_COMPUTED",
            "canterbury_policy": (
                "All six registered Canterbury files remain measured in results.tsv and "
                "effects.tsv but are excluded from broader claims."
            ),
        },
        "parameter_axes": {
            "var_h": {
                "parameter": "PPMd order",
                "levels": [4, 6, 8],
                "reported_effect": "adjacent charged-archive byte deltas per file at fixed memory",
            },
            "var_i": {
                "parameter": "requested PPMd memory MiB",
                "levels": [16, 64, 256],
                "reported_effect": "adjacent charged-archive byte deltas per file at fixed order",
            },
        },
        "validation": {
            "cell_status": "243/243 PASS",
            "encode_returncode": "243/243 zero",
            "inspection_returncode": "243/243 zero",
            "decode_returncode": "243/243 zero",
            "cmp_returncode": "243/243 zero",
            "cmp_equal": "243/243 true",
            "sha256_equal": "243/243 true",
            "round_trip": "243/243 true",
            "archive_authentication": "exact per-cell archive SHA-256 and fresh landed 7z inspection",
        },
    }


def _signed(value: str) -> str:
    number = int(value)
    return f"{number:+d}"


def _readme(effects: Sequence[Mapping[str, str]]) -> str:
    lines = [
        "# NEW-02 canonical PPMd oracle-grid results",
        "",
        "Date: 2026-08-10",
        "Status: `COMPLETE` source publication; `CHARACTERIZED_NO_SELECT` scientific outcome",
        "",
        "## Authority and boundary",
        "",
        f"The landed validator authenticated the immutable `{SOURCE_BASENAME}` publication:",
        f"exact main `{SOURCE_CODE_SHA}`, harness run ID `{SOURCE_RUN_ID}`, manifest",
        f"SHA-256 `{SOURCE_TOP_HASHES['MANIFEST.json']}`, and all 243 declared cells. Every cell",
        "encoded, underwent exact one-member PPMd inspection, decoded, passed `cmp -s`, and",
        "matched the frozen input SHA-256. `results.tsv` states all 243 outcomes and their",
        "measured timing/RSS values without any corpus-wide average.",
        "",
        "The preregistration contains no ceiling, aggregate, ranking, winner rule, or",
        "implementation-selection rule. Therefore this package does not select a parameter",
        "cell, issue GO/NO-GO, build a candidate, or compute a fraction of ceiling. The",
        "scientific result is characterization only: `NO-SELECT`.",
        "",
        "No systemd unit or systemd invocation ID is recorded by the canonical harness. The",
        "authenticated invocation identity is the harness run ID above; the absence of those",
        "two systemd fields is preserved explicitly in `provenance.json`, not inferred.",
        "",
        "## Var.H and Var.I per-file effects",
        "",
        "Var.H is the PPMd order axis (`4`, `6`, `8`). Var.I is requested PPMd memory",
        "(`16`, `64`, `256` MiB). Each archive triple is `16/64/256 MiB`. Order deltas are",
        "`4->6,6->8` at each fixed memory; memory deltas are `16->64,64->256` at each fixed",
        "order. A negative delta means the later level charged fewer archive bytes. These are",
        "exhaustive adjacent contrasts, not a ranking or selection rule.",
        "",
        "| cohort/file | order 4 archives | order 6 archives | order 8 archives | Var.H deltas at m16; m64; m256 | Var.I deltas at o4; o6; o8 |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in effects:
        marker = " †" if row["excluded_from_broad_claims"] == "true" else ""
        archive = {
            order: "/".join(row[f"o{order}_m{memory}_archive_bytes"] for memory in (16, 64, 256))
            for order in (4, 6, 8)
        }
        order_deltas = "; ".join(
            f"{_signed(row[f'o4_to_o6_at_m{memory}_delta_bytes'])},{_signed(row[f'o6_to_o8_at_m{memory}_delta_bytes'])}"
            for memory in (16, 64, 256)
        )
        memory_deltas = "; ".join(
            f"{_signed(row[f'm16_to_m64_at_o{order}_delta_bytes'])},{_signed(row[f'm64_to_m256_at_o{order}_delta_bytes'])}"
            for order in (4, 6, 8)
        )
        lines.append(
            f"| `{row['cohort']}/{row['file']}`{marker} | {archive[4]} | {archive[6]} | "
            f"{archive[8]} | {order_deltas} | {memory_deltas} |"
        )
    lines.extend(
        [
            "",
            "† Registered Canterbury file: measured in all nine cells and retained in both TSV",
            "files, but excluded from broader claims because fixed archive overhead dominates",
            "these small inputs. This package makes no broader aggregate claim in any case.",
            "",
            "## Files",
            "",
            "- `results.tsv`: all 243 authenticated cell outcomes, exact archive/input/decoded",
            "  identities, effective member method, measured timing/RSS, and round-trip gates.",
            "- `effects.tsv`: the exact 27 per-file archive matrices and exhaustive adjacent",
            "  Var.H/Var.I byte deltas shown above.",
            "- `provenance.json`: COMPLETE source, exact-main/run/tool identities, and explicit",
            "  absence of canonical systemd unit/invocation fields.",
            "- `summary.json`: structured `CHARACTERIZED_NO_SELECT` verdict and reporting bounds.",
            "- `SHA256SUMS`: deterministic package-data hashes.",
            "- `verify_new02_results.py` and `test_verify_new02_results.py`: fail-closed verifier,",
            "  raw re-authentication path, reproducible builder, and mutation tests.",
            "",
            "No database, API, site, backlog, candidate, or campaign state is changed by this",
            "package.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def build_package(raw_root: Path, output_dir: Path, *, replace: bool = False) -> None:
    """Rebuild all generated package files from one authenticated raw publication."""

    verify_raw_publication(raw_root)
    source = json.loads((raw_root / "provenance.json").read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise VerificationError("source provenance document is not an object")
    source_rows = _json_decimal(raw_root / "observations.jsonl")
    result_rows = _source_to_result_rows(source_rows)
    effects = _effect_rows(result_rows)
    if len(result_rows) != 243 or len(effects) != 27:
        raise VerificationError("source result cardinality is not exact 27/243")

    output_dir.mkdir(parents=True, exist_ok=True)
    if not replace and any((output_dir / name).exists() for name in (*GENERATED_FILES, "SHA256SUMS")):
        raise VerificationError("refusing to overwrite an existing generated result package")
    documents = {
        "README.md": _readme(effects).encode("utf-8"),
        "provenance.json": (json.dumps(_provenance_document(source), indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "results.tsv": _tsv_bytes(RESULT_COLUMNS, result_rows),
        "effects.tsv": _tsv_bytes(EFFECT_COLUMNS, effects),
        "summary.json": (json.dumps(_summary_document(), indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    for name in GENERATED_FILES:
        _write(output_dir / name, documents[name])
    ledger = "".join(
        f"{hashlib.sha256(documents[name]).hexdigest()}  {name}\n" for name in GENERATED_FILES
    )
    _write(output_dir / "SHA256SUMS", ledger.encode("ascii"))


def _read_tsv(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if tuple(reader.fieldnames or ()) != tuple(columns):
                raise VerificationError(f"{path.name} has an inexact header")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise VerificationError(f"{path.name} is invalid: {exc}") from exc
    if any(None in row or set(row) != set(columns) for row in rows):
        raise VerificationError(f"{path.name} has an inexact row schema")
    return rows


def _verify_hashes(root: Path, *, enforce_pinned_hashes: bool) -> None:
    ledger_path = root / "SHA256SUMS"
    try:
        lines = ledger_path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise VerificationError("SHA256SUMS is invalid") from exc
    expected_names = list(GENERATED_FILES)
    if len(lines) != len(expected_names):
        raise VerificationError("SHA256SUMS has an inexact entry count")
    for line, name in zip(lines, expected_names, strict=True):
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match.group(2) != name:
            raise VerificationError("SHA256SUMS has an inexact ordered entry")
        actual = sha256_file(root / name)
        if match.group(1) != actual:
            raise VerificationError(f"SHA256SUMS hash mismatch: {name}")
        if enforce_pinned_hashes and PINNED_HASHES.get(name) != actual:
            raise VerificationError(f"pinned hash mismatch: {name}")


def _exact_integer(value: str, label: str, *, nonnegative: bool = True) -> int:
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise VerificationError(f"{label} is not an exact integer")
    result = int(value)
    if nonnegative and result < 0:
        raise VerificationError(f"{label} is negative")
    return result


def _exact_decimal(value: str, label: str) -> Decimal:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value):
        raise VerificationError(f"{label} is not an exact nonnegative decimal")
    result = Decimal(value)
    if not result.is_finite() or result < 0:
        raise VerificationError(f"{label} is not finite and nonnegative")
    return result


def _verify_result_semantics(rows: Sequence[Mapping[str, str]]) -> None:
    historical = _load_historical_validator()
    expected_cells = []
    expected_records = []
    # Hash-authenticated frozen contract, read from the immutable raw
    # publication rather than from the capture harness.
    for item in historical.authenticated_inventory(Path(SOURCE_FINAL_NAMESPACE)):
        cohort = item["cohort"]
        name = item["name"]
        relative_path = item["relative_path"]
        size_bytes = item["size_bytes"]
        input_sha = item["sha256"]
        for order in historical.ORDERS:
            for memory in historical.MEMORY_MIB:
                expected_cells.append(f"{cohort}/{name}/order={order}/mem={memory}MiB")
                expected_records.append((cohort, name, relative_path, size_bytes, input_sha, order, memory))
    if len(rows) != 243 or [row["cell"] for row in rows] != expected_cells:
        raise VerificationError("results.tsv is not the exact ordered 243-cell grid")
    sha_pattern = re.compile(r"[0-9a-f]{64}")
    for index, (row, expected) in enumerate(zip(rows, expected_records, strict=True)):
        cohort, name, relative_path, size_bytes, input_sha, order, memory = expected
        excluded = str(relative_path).startswith("canterbury/")
        expected_method = (
                f"PPMD:o{order}:"
                f"mem{historical.expected_ppmd_memory_exponent(size_bytes, memory)}"
            )
        fixed = {
            "schema": PACKAGE_SCHEMA,
            "status": "PASS",
            "run_id": SOURCE_RUN_ID,
            "code_sha": SOURCE_CODE_SHA,
            "grid_index": str(index),
            "cell": expected_cells[index],
            "cohort": str(cohort),
            "file": str(name),
            "relative_path": str(relative_path),
            "excluded_from_broad_claims": str(excluded).lower(),
            "input_bytes": str(size_bytes),
            "input_sha256": str(input_sha),
            "order": str(order),
            "memory_mib": str(memory),
            "cpu_set": "0-15",
            "member_method": expected_method,
            "member_paths": json.dumps([name], separators=(",", ":")),
            "inspection_returncode": "0",
            "encode_returncode": "0",
            "decode_returncode": "0",
            "cmp_returncode": "0",
            "cmp_equal": "true",
            "sha256_equal": "true",
            "round_trip": "true",
            "decoded_bytes": str(size_bytes),
            "decoded_sha256": str(input_sha),
        }
        if any(row[key] != value for key, value in fixed.items()):
            raise VerificationError(f"source row semantics mismatch at grid index {index}")
        if _exact_integer(row["archive_bytes"], "archive_bytes") <= 0:
            raise VerificationError(f"source row archive bytes are not positive at grid index {index}")
        for key in ("archive_sha256", "encode_time_sha256", "decode_time_sha256"):
            if sha_pattern.fullmatch(row[key]) is None:
                raise VerificationError(f"source row {key} is invalid at grid index {index}")
        _exact_decimal(row["encode_elapsed_seconds"], "encode_elapsed_seconds")
        _exact_decimal(row["decode_elapsed_seconds"], "decode_elapsed_seconds")
        _exact_integer(row["encode_peak_rss_kib"], "encode_peak_rss_kib")
        _exact_integer(row["decode_peak_rss_kib"], "decode_peak_rss_kib")


def _verify_effect_semantics(results: Sequence[Mapping[str, str]], effects: Sequence[Mapping[str, str]]) -> None:
    expected = _effect_rows(results)
    for row in effects:
        expected_exclusion = str(row["relative_path"].startswith("canterbury/")).lower()
        if row["excluded_from_broad_claims"] != expected_exclusion:
            raise VerificationError("Canterbury exclusion policy mismatch")
    if len(effects) != 27 or effects != expected:
        raise VerificationError("effects.tsv effect delta or per-file matrix mismatch")


def _verify_documents(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    try:
        provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
        summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"structured result document is invalid: {exc}") from exc
    if not isinstance(provenance, dict) or not isinstance(summary, dict):
        raise VerificationError("structured result document is not an object")
    execution = provenance.get("execution_identity")
    source = provenance.get("source_publication")
    if not isinstance(execution, dict) or not isinstance(source, dict):
        raise VerificationError("provenance identity document is incomplete")
    if (
        provenance.get("schema") != PACKAGE_SCHEMA
        or source.get("status") != "COMPLETE"
        or source.get("final_namespace") != SOURCE_FINAL_NAMESPACE
        or source.get("observation_count") != 243
        or source.get("top_level_sha256") != SOURCE_TOP_HASHES
        or execution.get("exact_main_sha") != SOURCE_CODE_SHA
        or execution.get("harness_run_id") != SOURCE_RUN_ID
        or execution.get("systemd_unit") != "NOT_RECORDED_BY_CANONICAL_HARNESS"
        or execution.get("systemd_invocation_id") != "NOT_RECORDED_BY_CANONICAL_HARNESS"
    ):
        raise VerificationError("provenance identity document is inconsistent")
    verdict = summary.get("verdict")
    scope = summary.get("scope")
    if not isinstance(verdict, dict) or not isinstance(scope, dict):
        raise VerificationError("summary verdict document is incomplete")
    if (
        summary.get("schema") != PACKAGE_SCHEMA
        or verdict.get("outcome") != "CHARACTERIZED_NO_SELECT"
        or verdict.get("selection") != "NO-SELECT"
        or verdict.get("go_no_go") != "NOT_ISSUED"
        or verdict.get("candidate") != "NONE"
    ):
        raise VerificationError("summary must preserve the preregistered NO-SELECT boundary")
    if (
        verdict.get("ceiling") != "NOT_DEFINED_IN_PREREGISTRATION"
        or verdict.get("fraction_of_ceiling") != "NOT_COMPUTED"
        or scope.get("corpus_wide_average") != "NOT_COMPUTED"
        or scope.get("per_file_only") is not True
    ):
        raise VerificationError("summary ceiling/fraction/aggregate boundary mismatch")
    return provenance, summary


def verify_package(root: Path, *, enforce_pinned_hashes: bool = True) -> dict[str, object]:
    root = root.resolve()
    _verify_hashes(root, enforce_pinned_hashes=enforce_pinned_hashes)
    results = _read_tsv(root / "results.tsv", RESULT_COLUMNS)
    effects = _read_tsv(root / "effects.tsv", EFFECT_COLUMNS)
    _verify_result_semantics(results)
    _verify_effect_semantics(results, effects)
    provenance, summary = _verify_documents(root)
    return {
        "schema": PACKAGE_SCHEMA,
        "status": "PASS",
        "outcome": summary["verdict"]["outcome"],
        "source_status": provenance["source_publication"]["status"],
        "observation_count": len(results),
        "file_count": len(effects),
        "run_id": SOURCE_RUN_ID,
        "code_sha": SOURCE_CODE_SHA,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--raw-run", type=Path)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.build:
            if args.raw_run is None:
                raise VerificationError("--build requires --raw-run")
            build_package(args.raw_run, args.package, replace=args.replace)
        result = verify_package(args.package)
        if args.raw_run is not None and not args.build:
            verify_raw_publication(args.raw_run)
    except (VerificationError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"NEW02_RESULT_VERIFICATION=FAIL reason={exc}", file=sys.stderr)
        return 2
    print(
        "NEW02_RESULT_VERIFICATION=PASS "
        f"outcome={result['outcome']} source_status={result['source_status']} "
        f"cells={result['observation_count']} files={result['file_count']} "
        f"run_id={result['run_id']} code_sha={result['code_sha']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
