#!/usr/bin/env python3
"""Verify trial bundles and derive deterministic robust statistics."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from capabilities import PHASE_A_CODECS
from model import CODE_SHA_RE, SHA256_RE, require_finite_nonnegative


RESOURCE_METRIC_UNITS = {
    "compressed_bytes": "bytes",
    "compression_duration": "milliseconds",
    "decompression_duration": "milliseconds",
    "peak_memory": "bytes",
    "time_to_first_decoded_byte": "milliseconds",
    "energy": "joules",
}


def verify_bundle(bundle: dict[str, object]) -> None:
    if bundle.get("schema_version") != 1 or bundle.get("scope") != "resource_codec":
        raise ValueError("bundle must use resource_codec schema version 1")
    if "voids" in bundle:
        raise ValueError("void records must remain outside result bundles")
    environment = bundle.get("environment")
    if not isinstance(environment, dict) or not CODE_SHA_RE.fullmatch(
        str(environment.get("code_sha", ""))
    ):
        raise ValueError("environment code_sha is required")
    page_results = bundle.get("page_results")
    if page_results != {
        "explicit_wasm_application": [],
        "transparent_http_page": [],
    }:
        raise ValueError("Phase A page scopes must remain distinct and empty")
    trials = bundle.get("resource_results")
    if not isinstance(trials, list) or not trials:
        raise ValueError("bundle requires resource results")
    seen: set[tuple[str, str, int]] = set()
    for trial in trials:
        if not isinstance(trial, dict):
            raise ValueError("trial must be an object")
        _verify_trial(trial)
        key = (str(trial["sample_id"]), str(trial["codec_key"]), int(trial["trial_no"]))
        if key in seen:
            raise ValueError("duplicate trial")
        seen.add(key)


def _verify_trial(trial: dict[str, object]) -> None:
    if trial.get("codec_key") not in PHASE_A_CODECS:
        raise ValueError("trial codec is not in the Phase A allowlist")
    if not CODE_SHA_RE.fullmatch(str(trial.get("runner_code_sha", ""))) or not CODE_SHA_RE.fullmatch(
        str(trial.get("codec_code_sha", ""))
    ):
        raise ValueError("trial code SHA is required")
    for key in ("original_sha256", "compressed_sha256", "decoded_sha256"):
        if not SHA256_RE.fullmatch(str(trial.get(key, ""))):
            raise ValueError(f"{key} must be SHA-256")
    exact = (
        trial.get("roundtrip_exact") is True
        and trial["original_sha256"] == trial["decoded_sha256"]
        and trial.get("original_bytes") == trial.get("decoded_bytes")
    )
    if not exact:
        raise ValueError("trial round trip is not exact")
    metrics = trial.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError("trial metrics are required")
    unknown = set(metrics) - set(RESOURCE_METRIC_UNITS)
    if unknown:
        raise ValueError(f"unsupported resource metrics: {sorted(unknown)}")
    for name, value in metrics.items():
        require_finite_nonnegative(value, name)


def summarize_bundle(
    bundle: dict[str, object],
    *,
    seed: int = 74074,
    bootstrap_iterations: int = 5_000,
) -> dict[str, object]:
    verify_bundle(bundle)
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for trial in bundle["resource_results"]:
        for metric_name, value in trial["metrics"].items():
            grouped[(trial["sample_id"], trial["codec_key"], metric_name)].append(float(value))
    rng = random.Random(seed)
    summaries = []
    for (sample_id, codec_key, metric_name), values in sorted(grouped.items()):
        median = statistics.median(values)
        bootstrapped = _bootstrap_medians(values, bootstrap_iterations, rng)
        summaries.append(
            {
                "sample_id": sample_id,
                "codec_key": codec_key,
                "metric_name": metric_name,
                "unit": RESOURCE_METRIC_UNITS[metric_name],
                "median": _clean_number(median),
                "p95": _clean_number(_nearest_rank(values, 0.95)),
                "bootstrap_95": {
                    "low": _clean_number(min(median, _nearest_rank(bootstrapped, 0.025))),
                    "high": _clean_number(max(median, _nearest_rank(bootstrapped, 0.975))),
                },
                "sample_count": len(values),
            }
        )
    return {
        "schema_version": 1,
        "scope": "resource_codec",
        "seed": seed,
        "bootstrap_iterations": bootstrap_iterations,
        "summaries": summaries,
    }


def _bootstrap_medians(
    values: list[float],
    iterations: int,
    rng: random.Random,
) -> list[float]:
    if iterations <= 0:
        raise ValueError("bootstrap iterations must be positive")
    return [
        statistics.median(rng.choices(values, k=len(values)))
        for _ in range(iterations)
    ]


def _nearest_rank(values: Iterable[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot rank an empty series")
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def _clean_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=74074)
    parser.add_argument("--bootstrap-iterations", type=int, default=5_000)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    bundle = json.loads(args.fixture.read_text(encoding="utf-8"))
    summary = summarize_bundle(
        bundle,
        seed=args.seed,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
