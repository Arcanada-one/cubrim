#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path


REQUIRED_FILES = ("summary.json", "results.tsv", "provenance.json")
EXPECTED_SUMMARY_SHA256 = "dc504af5e98c34d9e84716f458b0e1b6ae0d68c55efb91bc74df0b17fcaa4dd0"
EXPECTED_RESULTS_SHA256 = "e7cc43de872bf6441302ee4f8288a8c6904d6a872d3d6271d5ade2bfe663d853"
EXPECTED_LEGACY_ROW_IDS = [185, 187, 190, 200, 205, 219, 224, 273, 325]
EXPECTED_CORE_ROWS_SHA256 = "105c981b58a703cab916f1a3a73f6b44102ece50407038b6e578647ed564db22"
EXPECTED_FOREIGN_REVISION = {
    "codec_rev": 1,
    "run_id": "stand-20260703-1500",
    "environment_label": "dev-ai stand multi-width-MED16",
    "matches_h07_source_commit": False,
}
EXPECTED_IMPLEMENTATION_BASE = {
    "origin_main_commit": "830a9a31deb00926a97f3fa5bd74f58003573fc0",
    "source_commit": "5357c3c16634db8b50b28dc94645f24afb24a4c2",
    "source_commit_is_ancestor": True,
    "commits_from_source_to_base": 343,
}
EXPECTED_SEALED_E1B = {
    "source_directory": "cubr-master-audit/CUBR-0046/e1b-results/H-07",
    "path_basis": "audit-workspace-relative",
    "summary": {
        "path": "summary.json",
        "sha256": EXPECTED_SUMMARY_SHA256,
    },
    "results": {
        "path": "results.tsv",
        "sha256": EXPECTED_RESULTS_SHA256,
    },
}
EXPECTED_CONSERVATIVE_INTERPRETATION = (
    "The sealed files are historical evidence, but the nine legacy rows identify a foreign "
    "codec revision rather than H-07 source commit 5357c3c. Without a proven row-to-source "
    "link, this package cannot promote H-07 to measured status and makes no GO claim."
)
RESULT_FIELDS = (
    "corpus",
    "file",
    "type",
    "orig",
    "comp",
    "ratio",
    "rt",
    "cmp",
    "mode",
    "compress_s",
    "decompress_s",
)
RESULT_FIELD_TYPES = {
    "corpus": str,
    "file": str,
    "type": str,
    "orig": int,
    "comp": int,
    "ratio": float,
    "rt": str,
    "cmp": int,
    "mode": str,
    "compress_s": float,
    "decompress_s": float,
}
EXPECTED_MANIFEST = {
    "schema_version": 1,
    "record_kind": "NONCANONICAL_PROVENANCE_NOTE",
    "canonical": False,
    "card_id": "H-07",
    "status": "HISTORICAL_PROVENANCE_INCOMPLETE",
    "measured": False,
    "implementation_base": EXPECTED_IMPLEMENTATION_BASE,
    "sealed_e1b": EXPECTED_SEALED_E1B,
    "legacy_database_provenance": {
        "row_ids": EXPECTED_LEGACY_ROW_IDS,
        "core_rows_sha256": EXPECTED_CORE_ROWS_SHA256,
        "relinking": "NOT_PERFORMED",
    },
    "foreign_revision_discrepancy": EXPECTED_FOREIGN_REVISION,
    "conservative_interpretation": EXPECTED_CONSERVATIVE_INTERPRETATION,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _parse_tsv_number(field: str, value: str, row_number: int) -> int | float:
    expected_type = RESULT_FIELD_TYPES[field]
    if expected_type is int:
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
            raise ValueError(f"results.tsv row {row_number} field {field} has wrong type")
        return int(value)
    try:
        parsed = json.loads(value, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"results.tsv row {row_number} field {field} has wrong type"
        ) from exc
    if type(parsed) is not float or not math.isfinite(parsed):
        raise ValueError(f"results.tsv row {row_number} field {field} has wrong type")
    return parsed


def load_results_rows(path: Path) -> list[dict[str, object]]:
    payload = path.read_bytes()
    # This one sealed historical artifact intentionally uses CRLF. The exception is
    # byte-exact and path-scoped; no JSON or other TSV whitespace is normalized.
    if (
        not payload.endswith(b"\r\n")
        or payload.count(b"\r\n") != 25
        or b"\n" in payload.replace(b"\r\n", b"")
        or b"\r" in payload.replace(b"\r\n", b"")
    ):
        raise ValueError("results.tsv must retain its sealed CRLF line endings")
    try:
        text = payload.decode("utf-8")
        rows = list(
            csv.reader(io.StringIO(text, newline=""), delimiter="\t", strict=True)
        )
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("results.tsv is not strict UTF-8 TSV") from exc
    if not rows or tuple(rows[0]) != RESULT_FIELDS:
        raise ValueError("results.tsv header mismatch")
    if len(rows) != 25:
        raise ValueError("results.tsv must contain exactly 24 data rows")
    parsed_rows: list[dict[str, object]] = []
    for row_number, values in enumerate(rows[1:], start=1):
        if len(values) != len(RESULT_FIELDS):
            raise ValueError(f"results.tsv row {row_number} field count mismatch")
        parsed: dict[str, object] = {}
        for field, value in zip(RESULT_FIELDS, values):
            expected_type = RESULT_FIELD_TYPES[field]
            parsed[field] = (
                value
                if expected_type is str
                else _parse_tsv_number(field, value, row_number)
            )
        parsed_rows.append(parsed)
    return parsed_rows


def verify_summary_results_parity(
    summary: dict[str, object], results_rows: list[dict[str, object]]
) -> None:
    per_file = summary.get("per_file")
    if not isinstance(per_file, list) or len(per_file) != 24:
        raise ValueError("summary must contain exactly 24 per_file rows")
    if type(summary.get("n_files")) is not int or summary.get("n_files") != 24:
        raise ValueError("summary n_files must be the integer 24")
    if len(results_rows) != 24:
        raise ValueError("results.tsv must contain exactly 24 data rows")
    for row_number, (summary_row, results_row) in enumerate(
        zip(per_file, results_rows), start=1
    ):
        if not isinstance(summary_row, dict) or set(summary_row) != set(RESULT_FIELDS):
            raise ValueError(f"summary row {row_number} field names mismatch")
        for field in RESULT_FIELDS:
            expected_type = RESULT_FIELD_TYPES[field]
            summary_value = summary_row[field]
            if type(summary_value) is not expected_type or (
                expected_type is float and not math.isfinite(summary_value)
            ):
                raise ValueError(
                    f"summary row {row_number} field {field} has wrong type"
                )
            if summary_value != results_row[field]:
                raise ValueError(
                    f"summary/results row {row_number} mismatch for {field}"
                )


def _verify_manifest_schema(actual: object, expected: object, path: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError(f"manifest schema mismatch at {path}")
        for key, expected_value in expected.items():
            child_path = key if path == "root" else f"{path}.{key}"
            _verify_manifest_schema(actual[key], expected_value, child_path)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"manifest schema mismatch at {path}")
        for index, (actual_value, expected_value) in enumerate(zip(actual, expected)):
            _verify_manifest_schema(actual_value, expected_value, f"{path}[{index}]")


def _verify_manifest_values(actual: object, expected: object, path: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise ValueError(f"manifest value/type mismatch at {path}")
        for key, expected_value in expected.items():
            child_path = key if path == "root" else f"{path}.{key}"
            _verify_manifest_values(actual[key], expected_value, child_path)
        return
    if isinstance(expected, list):
        if not isinstance(actual, list):
            raise ValueError(f"manifest value/type mismatch at {path}")
        for index, (actual_value, expected_value) in enumerate(zip(actual, expected)):
            _verify_manifest_values(actual_value, expected_value, f"{path}[{index}]")
        return
    if type(actual) is not type(expected) or actual != expected:
        raise ValueError(f"manifest value/type mismatch at {path}")


def verify(package_dir: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (package_dir / name).is_file()]
    if missing:
        raise ValueError(f"missing required files: {', '.join(missing)}")
    summary_path = package_dir / "summary.json"
    results_path = package_dir / "results.tsv"
    provenance_path = package_dir / "provenance.json"
    summary = load_json_object(summary_path, "summary.json")
    results_rows = load_results_rows(results_path)
    verify_summary_results_parity(summary, results_rows)
    summary_bytes = summary_path.read_bytes()
    if b"\r" in summary_bytes or not summary_bytes.endswith(b"\n"):
        raise ValueError("summary.json must retain its sealed LF-only line endings")
    if sha256(package_dir / "summary.json") != EXPECTED_SUMMARY_SHA256:
        raise ValueError("summary.json SHA-256 mismatch")
    if sha256(package_dir / "results.tsv") != EXPECTED_RESULTS_SHA256:
        raise ValueError("results.tsv SHA-256 mismatch")
    if b"\r" in provenance_path.read_bytes():
        raise ValueError("provenance.json must use LF-only line endings")
    provenance = load_json_object(provenance_path, "provenance.json")
    if "go" in provenance or "verdict" in provenance:
        raise ValueError("manifest must not assert a GO or verdict")
    _verify_manifest_schema(provenance, EXPECTED_MANIFEST, "root")
    if provenance.get("schema_version") != 1 or provenance.get("card_id") != "H-07":
        raise ValueError("manifest identity mismatch")
    if (
        provenance.get("record_kind") != "NONCANONICAL_PROVENANCE_NOTE"
        or provenance.get("canonical") is not False
        or provenance.get("status") != "HISTORICAL_PROVENANCE_INCOMPLETE"
        or provenance.get("measured") is not False
    ):
        raise ValueError("manifest must remain noncanonical, historical, and unmeasured")
    legacy = provenance.get("legacy_database_provenance", {})
    if legacy.get("row_ids") != EXPECTED_LEGACY_ROW_IDS:
        raise ValueError("legacy row provenance mismatch")
    if legacy.get("relinking") != "NOT_PERFORMED":
        raise ValueError("legacy rows must remain unrelinked")
    if legacy.get("core_rows_sha256") != EXPECTED_CORE_ROWS_SHA256:
        raise ValueError("legacy core-row hash mismatch")
    if provenance.get("foreign_revision_discrepancy") != EXPECTED_FOREIGN_REVISION:
        raise ValueError("foreign codec-revision discrepancy mismatch")
    if provenance.get("implementation_base") != EXPECTED_IMPLEMENTATION_BASE:
        raise ValueError("implementation ancestry mismatch")
    if provenance.get("sealed_e1b") != EXPECTED_SEALED_E1B:
        raise ValueError("sealed E1b source metadata mismatch")
    if provenance.get("conservative_interpretation") != EXPECTED_CONSERVATIVE_INTERPRETATION:
        raise ValueError("conservative interpretation mismatch")
    _verify_manifest_values(provenance, EXPECTED_MANIFEST, "root")


def main(argv: list[str]) -> int:
    package_dir = Path(argv[1]) if len(argv) == 2 else Path(__file__).resolve().parent
    try:
        verify(package_dir)
    except (OSError, ValueError) as exc:
        print(f"H-07 provenance package: FAIL: {exc}", file=sys.stderr)
        return 1
    print("H-07 provenance package: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
