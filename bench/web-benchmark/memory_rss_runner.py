#!/usr/bin/env python3
"""Measure CUBR-0075 whole-process RSS with one child per trial.

The existing Phase-A hypothesis probe intentionally keeps small decode timing
cells in one process.  That is not admissible for the ``memory-rss`` axis: a
run-level max-RSS value repeated across cells cannot support an RSS slope.  This
runner therefore creates the deterministic ladder once, then launches one
short-lived Rust process for every warmup and measured trial.  GNU ``time -v``
records the peak RSS of that trial process only.

The three explicit commands make interruption recoverable without weakening
the contract::

    --prepare       build payloads and content-addressed frame metadata
    --measure-sample  run exactly one sample's 3 warmups + 30 trials
    --aggregate     require all 13 sample results and derive the preregistered fit

No command writes the database or assigns evidence outside the staged bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hypothesis_runner import (
    CUBE_SIZES,
    RAW_SIZES,
    MeasurementVoid,
    _cpu_topology,
    _host_cpu_count,
    _read_temperature_celsius,
    _recheck_admission,
    _require_clean_tree,
    _deterministic_bytes,
    choose_cpu,
    sha256_file,
    write_payload,
)


TASK_ID = "CUBR-0075"
PHASE = "memory_rss"
TRIALS = 30
WARMUPS = 3
SEED = 75_075
BOOTSTRAP_ITERATIONS = 5_000
BOOTSTRAP_CONFIDENCE = 0.95
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBE = (
    REPO_ROOT / "code" / "cubrim-rs" / "target" / "release" / "examples" / "memory_rss_probe"
)
TIME_BINARY = Path("/usr/bin/time")
CODE_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
SAMPLE_IDS = {
    *(f"cube-{size}" for size in CUBE_SIZES),
    *(f"raw-store-{size}" for size in RAW_SIZES),
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MeasurementVoid(f"{path} must contain a JSON object")
    return value


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    value = completed.stdout.strip()
    if not CODE_SHA_RE.fullmatch(value):
        raise MeasurementVoid("source HEAD is not a lowercase Git SHA")
    return value


def choose_requested_cpu(requested: int | None) -> int:
    available = sorted(os.sched_getaffinity(0))
    if not available:
        raise MeasurementVoid("no CPU is available for the memory-rss runner")
    if requested is not None:
        if requested not in available:
            raise MeasurementVoid(f"requested CPU {requested} is outside process affinity")
        return requested
    return choose_cpu()


def ensure_singleton_affinity(argv: list[str], requested: int | None) -> int | None:
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) == 1:
        if requested is not None and affinity[0] != requested:
            raise MeasurementVoid(
                f"runner is pinned to CPU {affinity[0]}, not requested CPU {requested}"
            )
        return None
    taskset = shutil.which("taskset")
    if taskset is None:
        raise MeasurementVoid("taskset is required to pin the runner to one logical CPU")
    cpu = choose_requested_cpu(requested)
    completed = subprocess.run(
        [taskset, "--cpu-list", str(cpu), sys.executable, str(Path(__file__).resolve()), *argv],
        cwd=REPO_ROOT,
        check=False,
    )
    return completed.returncode


def admit_host(cpu: int) -> dict[str, Any]:
    affinity = sorted(os.sched_getaffinity(0))
    load_1m = os.getloadavg()[0]
    host_cpu_count = _host_cpu_count()
    temperatures = _read_temperature_celsius()
    topology = _cpu_topology(cpu)
    admission = {
        "accepted": bool(
            affinity == [cpu]
            and load_1m / host_cpu_count <= 1.0
            and temperatures
            and max(temperatures) < 90.0
            and topology is not None
        ),
        "load_1m": load_1m,
        "available_cpu_count": host_cpu_count,
        "process_affinity": affinity,
        "load_per_cpu": load_1m / host_cpu_count,
        "max_temperature_c": max(temperatures) if temperatures else None,
        "temperature_sample_count": len(temperatures),
        "max_load_per_cpu": 1.0,
        "max_temperature_c_exclusive": 90.0,
        "requested_cpu": cpu,
        "topology": topology,
        "effective_affinity": affinity,
        "taskset_required": True,
    }
    if not admission["accepted"]:
        raise MeasurementVoid(json.dumps({"reason": "failed_admission", **admission}, sort_keys=True))
    return admission


def manifest_samples(work_dir: Path, seed: int) -> list[dict[str, Any]]:
    payload_dir = work_dir / "payloads"
    samples: list[dict[str, Any]] = []
    for kind, sizes in (("cube", CUBE_SIZES), ("raw_store", RAW_SIZES)):
        for size in sizes:
            sample_id = f"{kind.replace('_', '-')}-{size}"
            filename = f"{sample_id}.payload"
            path = payload_dir / filename
            write_payload(path, size, kind, seed + size)
            samples.append(
                {
                    "sample_id": sample_id,
                    "path": str(Path("payloads") / filename),
                    "expected_mode": kind,
                    "input_bytes": size,
                    "input_sha256": sha256_file(path),
                }
            )
    return samples


def probe_sha(probe: Path) -> str:
    if not probe.is_file() or probe.is_symlink():
        raise MeasurementVoid(f"probe binary is missing or non-regular: {probe}")
    return sha256_file(probe)


def run_probe_json(command: list[str], *, timeout: float = 30.0) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise MeasurementVoid(
            f"memory-rss probe failed with {completed.returncode}: {completed.stderr.strip()}"
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise MeasurementVoid(f"memory-rss probe did not emit JSON: {error}") from error
    if not isinstance(value, dict):
        raise MeasurementVoid("memory-rss probe JSON is not an object")
    return value


def prepare(args: argparse.Namespace) -> None:
    _require_clean_tree()
    if not TIME_BINARY.is_file():
        raise MeasurementVoid("/usr/bin/time is required for per-process RSS")
    probe = args.probe.resolve()
    cpu = choose_requested_cpu(args.cpu)
    admission = admit_host(cpu)
    work_dir = args.work_dir.resolve()
    if (work_dir / "metadata.json").exists():
        raise MeasurementVoid(f"work directory already contains a prepared run: {work_dir}")
    work_dir.mkdir(parents=True, mode=0o700)
    samples = manifest_samples(work_dir, args.seed)
    manifest = {"schema_version": 1, "seed": args.seed, "samples": samples}
    manifest_path = work_dir / "manifest.json"
    write_json(manifest_path, manifest)
    prepared = run_probe_json([str(probe), "prepare", str(manifest_path)])
    if prepared.get("schema_version") != 1 or not isinstance(prepared.get("samples"), list):
        raise MeasurementVoid("probe prepared manifest has the wrong schema")
    prepared_by_id = {row.get("sample_id"): row for row in prepared["samples"]}
    if set(prepared_by_id) != SAMPLE_IDS:
        raise MeasurementVoid("probe prepared manifest does not cover the complete ladder")
    for sample in samples:
        row = prepared_by_id.get(sample["sample_id"])
        if not isinstance(row, dict) or row.get("input_sha256") != sample["input_sha256"]:
            raise MeasurementVoid(f"prepared input metadata changed for {sample['sample_id']}")
    write_json(work_dir / "prepared.json", prepared)
    source_sha = git_sha()
    metadata = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "phase": PHASE,
        "source_sha": source_sha,
        "probe_binary": str(probe),
        "probe_binary_sha256": probe_sha(probe),
        "manifest_sha256": sha256_file(manifest_path),
        "protocol": {
            "warmups": WARMUPS,
            "trials_per_cell": TRIALS,
            "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
            "bootstrap_confidence": BOOTSTRAP_CONFIDENCE,
            "seed": args.seed,
            "cpu": cpu,
            "roundtrip_gate": "sha256 and byte equality on every trial",
            "clock": "in-process cubrim encode/decode Instant::now",
            "rss_measurement": "GNU time -v peak RSS for one process per measured trial",
            "measurement_scope": "whole process including input, frame, decoder, and decoded output",
            "admission_recheck": "parent polls load, temperature, and singleton affinity",
        },
        "admission": admission,
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "prepared_at": iso_now(),
    }
    write_json(work_dir / "metadata.json", metadata)
    print(json.dumps({"status": "PREPARED", "work_dir": str(work_dir), "samples": len(samples), "cpu": cpu}, sort_keys=True))


def parse_peak_rss(report: str) -> int:
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", report)
    if match is None:
        raise MeasurementVoid("GNU time report omitted maximum resident set size")
    value = int(match.group(1)) * 1024
    if value <= 0:
        raise MeasurementVoid("GNU time reported a non-positive peak RSS")
    return value


def timed_trial(
    probe: Path,
    sample: dict[str, Any],
    payload: Path,
    work_dir: Path,
) -> dict[str, Any]:
    if not TIME_BINARY.is_file():
        raise MeasurementVoid("/usr/bin/time is required for per-process RSS")
    with tempfile.TemporaryDirectory(prefix="memory-rss-trial-", dir=work_dir) as directory:
        trial_dir = Path(directory)
        report = trial_dir / "time.txt"
        command = [
            str(TIME_BINARY),
            "--verbose",
            "--output",
            str(report),
            "--",
            str(probe),
            "trial",
            str(payload),
            str(sample["expected_mode"]),
            str(sample["input_sha256"]),
            str(sample["frame_sha256"]),
            str(sample["sample_id"]),
        ]
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if completed.returncode != 0:
            raise MeasurementVoid(
                f"{sample['sample_id']} trial failed with {completed.returncode}: {completed.stderr.strip()}"
            )
        if not report.is_file():
            raise MeasurementVoid(f"{sample['sample_id']} trial omitted GNU time report")
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise MeasurementVoid(f"{sample['sample_id']} trial emitted invalid JSON: {error}") from error
        if not isinstance(value, dict):
            raise MeasurementVoid(f"{sample['sample_id']} trial JSON is not an object")
        if value.get("roundtrip_exact") is not True or value.get("decoded_sha256") != sample["input_sha256"]:
            raise MeasurementVoid(f"{sample['sample_id']} trial failed the exact round-trip gate")
        if value.get("frame_sha256") != sample["frame_sha256"]:
            raise MeasurementVoid(f"{sample['sample_id']} trial changed its frame hash")
        value["peak_rss_bytes"] = parse_peak_rss(report.read_text(encoding="utf-8"))
        return value


def measure_sample(args: argparse.Namespace) -> None:
    _require_clean_tree()
    work_dir = args.work_dir.resolve()
    metadata = read_json(work_dir / "metadata.json")
    prepared = read_json(work_dir / "prepared.json")
    source_sha = git_sha()
    if metadata.get("source_sha") != source_sha:
        raise MeasurementVoid("source HEAD changed after preparation; refusing mixed-head evidence")
    probe = args.probe.resolve()
    if metadata.get("probe_binary_sha256") != probe_sha(probe):
        raise MeasurementVoid("probe binary changed after preparation")
    cpu = int(metadata["protocol"]["cpu"])
    admission = admit_host(cpu)
    if admission["effective_affinity"] != [cpu]:
        raise MeasurementVoid("measurement runner is not pinned to the prepared CPU")
    prepared_by_id = {row.get("sample_id"): row for row in prepared.get("samples", [])}
    sample = prepared_by_id.get(args.sample_id)
    if not isinstance(sample, dict):
        raise MeasurementVoid(f"unknown sample {args.sample_id}")
    result_dir = work_dir / "results"
    result_path = (args.out.resolve() if args.out else result_dir / f"{args.sample_id}.json")
    if result_path.exists():
        raise MeasurementVoid(f"sample result already exists: {result_path}")
    payload = work_dir / str(sample["path"])
    if not payload.is_file() or payload.is_symlink():
        raise MeasurementVoid(f"sample payload is not a regular file: {payload}")
    for _ in range(WARMUPS):
        timed_trial(probe, sample, payload, work_dir)
    trials: list[dict[str, Any]] = []
    for trial_no in range(1, TRIALS + 1):
        if trial_no == 1 or trial_no % 5 == 0:
            _recheck_admission(cpu, int(metadata["admission"]["available_cpu_count"]))
        row = timed_trial(probe, sample, payload, work_dir)
        row["trial_no"] = trial_no
        row["randomized_order"] = 1
        row["measured_at"] = iso_now()
        trials.append(row)
    result = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "phase": PHASE,
        "source_sha": source_sha,
        "probe_binary_sha256": metadata["probe_binary_sha256"],
        "sample": {**sample, "trials": trials},
        "measured_at": iso_now(),
    }
    write_json(result_path, result)
    print(json.dumps({"status": "MEASURED", "sample_id": args.sample_id, "trials": len(trials), "out": str(result_path)}, sort_keys=True))


def nearest_rank(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))]


def bootstrap_median(values: list[float], seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    medians = [median([rng.choice(values) for _ in values]) for _ in range(BOOTSTRAP_ITERATIONS)]
    return {
        "median": float(median(values)),
        "low": nearest_rank(medians, 0.025),
        "high": nearest_rank(medians, 0.975),
    }


def median(values: list[float]) -> float:
    return nearest_rank(values, 0.5)


def linear_fit(points: list[tuple[float, float]]) -> dict[str, float]:
    if len(points) < 2:
        raise MeasurementVoid("RSS fit requires at least two complete sample points")
    x_bar = sum(x for x, _ in points) / len(points)
    y_bar = sum(y for _, y in points) / len(points)
    denominator = sum((x - x_bar) ** 2 for x, _ in points)
    if denominator <= 0:
        raise MeasurementVoid("RSS fit has no input-size variance")
    slope = sum((x - x_bar) * (y - y_bar) for x, y in points) / denominator
    intercept = y_bar - slope * x_bar
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in points)
    total = sum((y - y_bar) ** 2 for _, y in points)
    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": 1.0 if total == 0 else 1.0 - residual / total,
        "point_count": len(points),
        "fit": "ordinary_least_squares_peak_rss_bytes_vs_decoded_bytes",
    }


def aggregate(args: argparse.Namespace) -> None:
    _require_clean_tree()
    work_dir = args.work_dir.resolve()
    metadata = read_json(work_dir / "metadata.json")
    prepared = read_json(work_dir / "prepared.json")
    if metadata.get("source_sha") != git_sha():
        raise MeasurementVoid("source HEAD changed before aggregation")
    prepared_samples = prepared.get("samples")
    if not isinstance(prepared_samples, list):
        raise MeasurementVoid("prepared sample list is missing")
    if {row.get("sample_id") for row in prepared_samples} != SAMPLE_IDS:
        raise MeasurementVoid("prepared sample set is incomplete")
    results: list[dict[str, Any]] = []
    for sample in sorted(prepared_samples, key=lambda row: str(row["sample_id"])):
        result_path = work_dir / "results" / f"{sample['sample_id']}.json"
        result = read_json(result_path)
        if result.get("source_sha") != metadata.get("source_sha"):
            raise MeasurementVoid(f"{sample['sample_id']} result came from another source head")
        measured = result.get("sample")
        if not isinstance(measured, dict) or measured.get("sample_id") != sample["sample_id"]:
            raise MeasurementVoid(f"{sample['sample_id']} result identity is invalid")
        trials = measured.get("trials")
        if not isinstance(trials, list) or len(trials) != TRIALS:
            raise MeasurementVoid(f"{sample['sample_id']} does not contain exactly {TRIALS} trials")
        if measured.get("input_sha256") != sample.get("input_sha256") or measured.get("frame_sha256") != sample.get("frame_sha256"):
            raise MeasurementVoid(f"{sample['sample_id']} content hashes disagree with preparation")
        trial_numbers = {trial.get("trial_no") for trial in trials}
        if trial_numbers != set(range(1, TRIALS + 1)):
            raise MeasurementVoid(f"{sample['sample_id']} trial numbering is incomplete")
        for trial in trials:
            if trial.get("roundtrip_exact") is not True or trial.get("decoded_sha256") != sample["input_sha256"]:
                raise MeasurementVoid(f"{sample['sample_id']} contains a non-exact trial")
            if not isinstance(trial.get("peak_rss_bytes"), int) or trial["peak_rss_bytes"] <= 0:
                raise MeasurementVoid(f"{sample['sample_id']} contains an invalid RSS observation")
        results.append(measured)

    cells: list[dict[str, Any]] = []
    fit_points: list[tuple[float, float]] = []
    for index, sample in enumerate(results):
        rss = [float(trial["peak_rss_bytes"]) for trial in sample["trials"]]
        summary = bootstrap_median(rss, int(metadata["protocol"]["seed"]) + index)
        cells.append(
            {
                "sample_id": sample["sample_id"],
                "ladder": sample["expected_mode"],
                "mode": sample["expected_mode"],
                "input_bytes": sample["input_bytes"],
                "frame_bytes": sample["frame_bytes"],
                "input_sha256": sample["input_sha256"],
                "frame_sha256": sample["frame_sha256"],
                "peak_rss_bytes": summary,
                "trial_count": len(sample["trials"]),
            }
        )
        fit_points.append((float(sample["input_bytes"]), summary["median"]))
    fit = linear_fit(fit_points)
    slope = fit["slope"]
    intercept = fit["intercept"]
    decision = "WIN" if slope <= 1.5 else "GO" if slope <= 2.5 and intercept <= 16 * 1024 * 1024 else "NO-GO"
    source_sha = str(metadata["source_sha"])
    bundle = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "phase": PHASE,
        "source_sha": source_sha,
        "runner_sha": source_sha,
        "probe_binary": metadata["probe_binary"],
        "probe_binary_sha256": metadata["probe_binary_sha256"],
        "manifest": {
            "schema_version": 1,
            "seed": metadata["protocol"]["seed"],
            "sha256": metadata["manifest_sha256"],
            "samples": [
                {
                    "sample_id": sample["sample_id"],
                    "path": sample["path"],
                    "expected_mode": sample["expected_mode"],
                    "input_bytes": sample["input_bytes"],
                    "input_sha256": sample["input_sha256"],
                    "frame_bytes": sample["frame_bytes"],
                    "frame_sha256": sample["frame_sha256"],
                }
                for sample in results
            ],
        },
        "protocol": metadata["protocol"],
        "admission": metadata["admission"],
        "host": metadata["host"],
        "samples": results,
        "evaluation": {
            "cells": cells,
            "fit": fit,
            "derived": {
                "rss-slope": {
                    "ladder_key": "all-samples",
                    "metric_name": "rss_slope",
                    "unit": "bytes_per_byte",
                    "value": slope,
                    "point_count": fit["point_count"],
                    "r_squared": fit["r_squared"],
                    "complete": True,
                },
                "rss-intercept": {
                    "ladder_key": "all-samples",
                    "metric_name": "rss_intercept",
                    "unit": "bytes",
                    "value": intercept,
                    "point_count": fit["point_count"],
                    "r_squared": fit["r_squared"],
                    "complete": True,
                },
            },
            "decision": decision,
        },
        "publication": {
            "state": "staged",
            "disclosure_status_reference": os.environ.get(
                "CUBRIM_DISCLOSURE_STATUS_REFERENCE", "LEGAL-0061:terminal-compliant"
            ),
            "database_write": False,
        },
        "prepared_at": metadata["prepared_at"],
        "completed_at": iso_now(),
    }
    if not CODE_SHA_RE.fullmatch(source_sha):
        raise MeasurementVoid("aggregate source SHA is invalid")
    write_json(args.out.resolve(), bundle)
    print(
        json.dumps(
            {
                "status": "PASS",
                "out": str(args.out.resolve()),
                "samples": len(results),
                "trials": len(results) * TRIALS,
                "rss_slope": slope,
                "rss_intercept": intercept,
                "r_squared": fit["r_squared"],
                "decision": decision,
            },
            sort_keys=True,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--prepare", action="store_true")
    command.add_argument("--measure-sample", action="store_true")
    command.add_argument("--aggregate", action="store_true")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--sample-id")
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def main(argv: list[str] | None = None) -> int:
    args = parse_args() if argv is None else parse_args()
    raw_argv = sys.argv[1:] if argv is None else argv
    try:
        reexec_returncode = ensure_singleton_affinity(raw_argv, args.cpu)
        if reexec_returncode is not None:
            return reexec_returncode
        if args.prepare:
            prepare(args)
        elif args.measure_sample:
            if not args.sample_id:
                raise MeasurementVoid("--sample-id is required with --measure-sample")
            measure_sample(args)
        else:
            if not args.out:
                raise MeasurementVoid("--out is required with --aggregate")
            aggregate(args)
        return 0
    except (MeasurementVoid, OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "VOID", "reason": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
