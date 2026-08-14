#!/usr/bin/env python3
"""Validate and aggregate the paired transparent-HTTP page proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from chromium.netlog_verify import verify_payload

METRICS = (
    "time_to_first_byte",
    "first_contentful_paint",
    "largest_contentful_paint",
    "total_blocking_time",
    "page_load_duration",
)
ARMS = ("cbm", "identity")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _require_metric(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return float(value)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1))
    return ordered[index]


def _summary(arm: str, metric: str, values: list[float], trials: list[int]) -> dict[str, Any]:
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return {
        "page_id": "transparent-http-home-v1",
        "delivery": arm,
        "metric_name": metric,
        "unit": "milliseconds",
        "median": median,
        "p95": _percentile(values, 0.95),
        "sample_count": len(values),
        "trial_numbers": sorted(trials),
    }


def _validate_metadata(metadata: dict[str, Any]) -> None:
    if metadata.get("schema_version") != 1:
        raise ValueError("metadata schema version is invalid")
    for key in ("source_sha", "chromium_source_sha"):
        if not isinstance(metadata.get(key), str) or not COMMIT_RE.fullmatch(metadata[key]):
            raise ValueError(f"metadata {key} is invalid")
    _require_sha(metadata.get("browser_sha256"), "metadata browser_sha256")
    if not isinstance(metadata.get("browser_version"), str) or not metadata["browser_version"].strip():
        raise ValueError("metadata browser_version is invalid")
    if not isinstance(metadata.get("document"), str) or not metadata["document"].strip():
        raise ValueError("metadata document is invalid")


def _validate_schedule(path: Path, trials: int, warmups: int) -> None:
    if not path.is_file():
        raise ValueError("randomized schedule is missing")
    observed: list[tuple[str, str, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) != 3 or fields[0] not in {"warmup", "trial"} or fields[1] not in ARMS:
            raise ValueError("randomized schedule contains an invalid row")
        try:
            number = int(fields[2])
        except ValueError as error:
            raise ValueError("randomized schedule contains an invalid trial number") from error
        observed.append((fields[0], fields[1], number))
    expected = {
        (kind, arm, number)
        for kind, count in (("warmup", warmups), ("trial", trials))
        for arm in ARMS
        for number in range(1, count + 1)
    }
    if len(observed) != len(expected) or set(observed) != expected:
        raise ValueError("randomized schedule is incomplete or duplicated")


def _validate_row(row: dict[str, Any], origin: bytes, screenshot: bytes, label: str) -> None:
    if row.get("schema_version") != 1:
        raise ValueError(f"{label} row schema version is invalid")
    body = row.get("body")
    if not isinstance(body, dict) or body.get("status") != 200 or body.get("roundtrip_exact") is not True:
        raise ValueError(f"{label} body proof is incomplete")
    origin_sha = hashlib.sha256(origin).hexdigest()
    if body.get("byte_length") != len(origin) or body.get("origin_byte_length") != len(origin):
        raise ValueError(f"{label} body length does not match origin")
    if body.get("sha256") != origin_sha or body.get("origin_sha256") != origin_sha:
        raise ValueError(f"{label} body hash does not match origin")
    screenshot_info = row.get("screenshot")
    screenshot_sha = hashlib.sha256(screenshot).hexdigest()
    if not isinstance(screenshot_info, dict) or screenshot_info.get("byte_length") != len(screenshot) or screenshot_info.get("sha256") != screenshot_sha:
        raise ValueError(f"{label} screenshot proof is invalid")
    metrics = row.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != set(METRICS):
        raise ValueError(f"{label} metric set is incomplete")
    for name in METRICS:
        _require_metric(metrics[name], f"{label}.{name}")


def _arm_rows(root: Path, arm: str, origin: bytes, document: str, trials: int, warmups: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    arm_root = root / arm
    if not arm_root.is_dir():
        raise ValueError(f"missing {arm} arm")
    groups: list[tuple[str, int, str]] = [("warmups", warmups, "warmup"), ("trials", trials, "trial")]
    collected: list[list[dict[str, Any]]] = []
    for directory, count, prefix in groups:
        files = sorted((arm_root / directory).glob("*.json"))
        if len(files) != count:
            raise ValueError(f"{arm} arm must contain exactly {count} {directory[:-1]} rows")
        rows: list[dict[str, Any]] = []
        for number, path in enumerate(files, start=1):
            expected_name = f"{prefix}-{number:02d}.json"
            if path.name != expected_name:
                raise ValueError(f"{arm} {directory} filename set is not contiguous")
            row = _load(path)
            screenshot_path = arm_root / "screenshots" / f"{prefix}-{number:02d}.png"
            netlog_path = arm_root / "netlogs" / f"{prefix}-{number:02d}.json"
            if not screenshot_path.is_file() or not netlog_path.is_file():
                raise ValueError(f"{arm} {prefix} {number} is missing proof files")
            _validate_row(row, origin, screenshot_path.read_bytes(), f"{arm} {prefix} {number}")
            evidence = verify_payload(_load(netlog_path), document, expected_encoding=arm)
            if not evidence.verdict:
                raise ValueError(f"{arm} {prefix} {number} failed netlog transport proof")
            row["_proof"] = {
                "netlog_sha256": _sha256(netlog_path),
                "screenshot_sha256": _sha256(screenshot_path),
                "transport_verified": True,
            }
            rows.append(row)
        collected.append(rows)
    return collected[0], collected[1]


def build_bundle(root: Path, origin_path: Path, *, trials: int = 30, warmups: int = 3) -> dict[str, Any]:
    if trials < 1 or warmups < 1:
        raise ValueError("trials and warmups must be positive")
    metadata = _load(root / "metadata.json")
    _validate_metadata(metadata)
    schedule_path = root / "schedule.tsv"
    _validate_schedule(schedule_path, trials, warmups)
    origin = origin_path.read_bytes()
    arm_data = {
        arm: _arm_rows(root, arm, origin, metadata["document"], trials, warmups)
        for arm in ARMS
    }
    page_results: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for arm in ARMS:
        _, measured = arm_data[arm]
        for trial_no, row in enumerate(measured, start=1):
            page_results.append({
                "page_id": "transparent-http-home-v1",
                "delivery": arm,
                "trial_no": trial_no,
                "network_provenance": {
                    "transport": "http_loopback",
                    "delivery": "transparent_http_page",
                    "content_encoding": arm,
                    "cache_policy": "no-store",
                    "netlog": row["_proof"],
                },
                "body": row["body"],
                "screenshot": row["screenshot"],
                "metrics": {
                    name: _require_metric(row["metrics"][name], name) for name in METRICS
                },
            })
        for metric in METRICS:
            summaries.append(_summary(
                arm,
                metric,
                [float(row["metrics"][metric]) for row in measured],
                list(range(1, trials + 1)),
            ))
    by_key = {(row["delivery"], row["metric_name"]): row for row in summaries}
    comparison = []
    for metric in METRICS:
        identity = by_key[("identity", metric)]["median"]
        cbm = by_key[("cbm", metric)]["median"]
        comparison.append({
            "metric_name": metric,
            "identity_median": identity,
            "cbm_median": cbm,
            "cbm_minus_identity": cbm - identity,
        })
    return {
        "schema_version": 1,
        "scope": "page_metrics",
        "phase": "B",
        "scenario": "transparent_http_page",
        "page": {
            "page_id": "transparent-http-home-v1",
            "document": metadata["document"],
            "origin_bytes": len(origin),
            "origin_sha256": hashlib.sha256(origin).hexdigest(),
            "composition": {"delivery": "transparent_http_page", "arms": list(ARMS)},
        },
        "corpus": {"kind": "single_document_fixture"},
        "toolchain": [{"name": "chromium-content-shell", "version": metadata["browser_version"], "sha256": metadata["browser_sha256"]}],
        "protocol": {
            "warmups": warmups,
            "trials_per_arm": trials,
            "arms": list(ARMS),
            "metrics": list(METRICS),
            "navigation": "fresh_content_shell_process_per_trial",
            "cache_policy": "no-store",
            "network_isolation": "loopback_only",
            "transport_verifier": "chromium/netlog_verify.py",
            "randomized_order_seed": 72072,
            "schedule_sha256": _sha256(schedule_path),
        },
        "provenance": metadata,
        "page_results": page_results,
        "page_summaries": summaries,
        "comparison": comparison,
        "transparent_http_page": {"available": True, "transport_verified": True},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--origin", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    args = parser.parse_args()
    bundle = build_bundle(args.root.resolve(strict=True), args.origin.resolve(strict=True), trials=args.trials, warmups=args.warmups)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"bundle": str(args.out), "scenario": bundle["scenario"], "trials_per_arm": args.trials}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
