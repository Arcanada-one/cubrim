#!/usr/bin/env python3
"""Admission, provenance, and schema gate for CUBR-0075 allocator telemetry."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = (
    REPO_ROOT
    / "documentation"
    / "ephemeral"
    / "research"
    / "CUBR-0075-ALLOCATOR-TELEMETRY-PREREG-20260814.md"
)
SAMPLES = 13
PROFILES = ("static_profile", "dynamic_profile")
TRIALS = 30
WARMUPS = 3
SEED = 75_075
HEX64 = set("0123456789abcdef")


class MeasurementVoid(RuntimeError):
    """A protocol or provenance failure that cannot be scored as a result."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise MeasurementVoid(f"git rev-parse failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def require_clean_tree() -> None:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise MeasurementVoid(f"git status failed: {completed.stderr.strip()}")
    if completed.stdout.strip():
        raise MeasurementVoid("worktree is dirty; measurement requires an exact clean source")


def _read_temperatures() -> list[float]:
    readings: list[float] = []
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            readings.append(int(path.read_text(encoding="ascii").strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    if readings:
        return readings
    for name_path in sorted(Path("/sys/class/hwmon").glob("hwmon*/name")):
        for path in sorted(name_path.parent.glob("temp*_input")):
            try:
                readings.append(int(path.read_text(encoding="ascii").strip()) / 1000.0)
            except (OSError, ValueError):
                continue
    return readings


def admission() -> dict[str, Any]:
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) != 1:
        raise MeasurementVoid(f"probe is not singleton-pinned: affinity={affinity}")
    cpu_count = os.cpu_count() or 1
    load_per_cpu = os.getloadavg()[0] / cpu_count
    temperatures = _read_temperatures()
    if load_per_cpu > 1.0:
        raise MeasurementVoid(f"load admission failed: {load_per_cpu:.6f} per CPU")
    if not temperatures:
        raise MeasurementVoid("temperature admission failed: no readable sensor")
    max_temperature = max(temperatures)
    if max_temperature >= 90.0:
        raise MeasurementVoid(f"temperature admission failed: {max_temperature:.3f} C")
    return {
        "hostname": platform.node(),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "effective_affinity": affinity,
        "load_per_cpu": load_per_cpu,
        "max_temperature_c": max_temperature,
        "cpu_topology": {"logical_cpus": cpu_count},
    }


def taskset_argv(cpu: int, args: list[str]) -> list[str]:
    taskset = shutil.which("taskset")
    if taskset is None:
        raise MeasurementVoid("taskset is required to establish singleton affinity")
    return [taskset, "--cpu-list", str(cpu), sys.executable, str(Path(__file__).resolve()), *args]


def append_journal(path: Path, event: str, **fields: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"event": event, "recorded_at_epoch": time.time(), **fields}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _hex_digest(value: Any, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in HEX64 for char in value):
        raise MeasurementVoid(f"{field} is not a lowercase SHA-256 digest")


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MeasurementVoid(f"{field} must be a non-negative integer")
    return value


def _trials(bundle: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for sample in bundle["results"]:
        for profile_name in PROFILES:
            yield from sample[profile_name]["trials"]


def summarize(bundle: dict[str, Any]) -> dict[str, Any]:
    rows = list(_trials(bundle))
    max_largest = max(row["largest_single_allocation_bytes"] for row in rows)
    max_ratio = max(row["auxiliary_memory_bound_ratio"] for row in rows)
    win_largest = max_largest <= 65_536
    go_largest = max_largest <= 4_194_304
    go_auxiliary = max_ratio <= 1.0
    decision = "WIN" if win_largest and go_auxiliary else "GO" if go_largest and go_auxiliary else "NO_GO"
    return {
        "max_largest_single_allocation_bytes": max_largest,
        "max_auxiliary_memory_bound_ratio": max_ratio,
        "win_largest_single_allocation_bytes": win_largest,
        "go_largest_single_allocation_bytes": go_largest,
        "go_auxiliary_memory_bound_ratio": go_auxiliary,
        "decision": decision,
    }


def validate_bundle(bundle: dict[str, Any], expected_source_sha: str | None = None) -> dict[str, Any]:
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        raise MeasurementVoid("bundle schema_version must be 1")
    if bundle.get("task_id") != "CUBR-0075" or bundle.get("phase") != "allocator_telemetry":
        raise MeasurementVoid("bundle task/phase identity is invalid")
    protocol = bundle.get("protocol")
    if protocol != {
        "samples": SAMPLES,
        "profiles": 2,
        "warmups": WARMUPS,
        "trials": TRIALS,
        "seed": SEED,
        "chunk_size": 65_536,
        "block_size": 65_536,
    }:
        raise MeasurementVoid(f"protocol is not the frozen 3/30/13-cell contract: {protocol!r}")
    provenance = bundle.get("provenance")
    if not isinstance(provenance, dict):
        raise MeasurementVoid("bundle provenance is missing")
    required_provenance = ("runner_sha", "probe_sha", "binary_sha", "manifest_sha", "preregistration_sha")
    for field in required_provenance:
        _hex_digest(provenance.get(field), f"provenance.{field}")
    source_sha = provenance.get("source_sha")
    if not isinstance(source_sha, str) or not source_sha:
        raise MeasurementVoid("provenance.source_sha is missing")
    if expected_source_sha is not None and source_sha != expected_source_sha:
        raise MeasurementVoid(f"source SHA mismatch: {source_sha} != {expected_source_sha}")
    results = bundle.get("results")
    if not isinstance(results, list) or len(results) != SAMPLES:
        raise MeasurementVoid(f"expected exactly {SAMPLES} samples")
    for sample in results:
        if not isinstance(sample, dict) or not sample.get("sample_id") or not sample.get("path"):
            raise MeasurementVoid("sample identity is incomplete")
        _nonnegative_int(sample.get("input_bytes"), f"{sample.get('sample_id')}.input_bytes")
        _hex_digest(sample.get("input_sha256"), f"{sample.get('sample_id')}.input_sha256")
        for profile_name in PROFILES:
            profile = sample.get(profile_name)
            if not isinstance(profile, dict) or profile.get("mode") not in {"web", "raw_store"}:
                raise MeasurementVoid(f"{sample.get('sample_id')} has invalid {profile_name}")
            _nonnegative_int(profile.get("frame_bytes"), f"{sample.get('sample_id')}.{profile_name}.frame_bytes")
            _hex_digest(profile.get("frame_sha256"), f"{sample.get('sample_id')}.{profile_name}.frame_sha256")
            trials = profile.get("trials")
            if not isinstance(trials, list) or len(trials) != TRIALS:
                raise MeasurementVoid(f"{sample.get('sample_id')} {profile_name} must contain {TRIALS} trials")
            trial_numbers = [trial.get("trial_no") for trial in trials if isinstance(trial, dict)]
            if sorted(trial_numbers) != list(range(1, TRIALS + 1)):
                raise MeasurementVoid(f"{sample.get('sample_id')} {profile_name} trial numbers are not exact")
            for trial in trials:
                if trial.get("roundtrip_exact") is not True:
                    raise MeasurementVoid("roundtrip_exact is not true for every trial")
                _hex_digest(trial.get("decoded_sha256"), "trial.decoded_sha256")
                numeric_fields = (
                    "allocation_count",
                    "allocated_bytes",
                    "deallocated_bytes",
                    "peak_live_bytes",
                    "largest_single_allocation_bytes",
                    "live_bytes_after",
                    "caller_input_bytes",
                    "declared_output_bytes",
                    "decoder_retained_peak_bytes",
                    "decoder_retained_after_drop_bytes",
                    "auxiliary_peak_bytes",
                    "auxiliary_ratio_numerator_bytes",
                    "auxiliary_ratio_denominator_bytes",
                )
                for field in numeric_fields:
                    _nonnegative_int(trial.get(field), f"trial.{field}")
                if trial["deallocated_bytes"] > trial["allocated_bytes"]:
                    raise MeasurementVoid("deallocated bytes exceed allocated bytes")
                if trial["caller_input_bytes"] == 0 or trial["auxiliary_ratio_denominator_bytes"] != trial["caller_input_bytes"]:
                    raise MeasurementVoid("auxiliary ratio denominator is not the caller input size")
                if trial["auxiliary_ratio_numerator_bytes"] != trial["auxiliary_peak_bytes"]:
                    raise MeasurementVoid("auxiliary ratio numerator is not the auxiliary peak")
                ratio = trial.get("auxiliary_memory_bound_ratio")
                if isinstance(ratio, bool) or not isinstance(ratio, (float, int)) or not math.isfinite(ratio):
                    raise MeasurementVoid("auxiliary ratio is not finite")
                expected_ratio = trial["auxiliary_peak_bytes"] / trial["caller_input_bytes"]
                if not math.isclose(float(ratio), expected_ratio, rel_tol=1e-12, abs_tol=1e-12):
                    raise MeasurementVoid("auxiliary ratio does not match its operands")
                minimum_capacity = trial["caller_input_bytes"] + trial["declared_output_bytes"] + trial["auxiliary_peak_bytes"]
                if trial["decoder_retained_peak_bytes"] < minimum_capacity:
                    raise MeasurementVoid("decoder retained peak is below its recorded components")
    expected_summary = summarize(bundle)
    if bundle.get("summary") != expected_summary:
        raise MeasurementVoid("summary is not derived from the raw trial rows")
    return bundle


def _environment_vars(admitted: dict[str, Any], runner_sha: str, prereg_sha: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "CUBRIM_EFFECTIVE_AFFINITY": json.dumps(admitted["effective_affinity"]),
            "CUBRIM_LOAD_PER_CPU": str(admitted["load_per_cpu"]),
            "CUBRIM_MAX_TEMPERATURE_C": str(admitted["max_temperature_c"]),
            "CUBRIM_RUNNER_SHA": runner_sha,
            "CUBRIM_PREREG_SHA": prereg_sha,
        }
    )
    return env


def run(args: argparse.Namespace) -> int:
    manifest = Path(args.manifest).resolve()
    probe = Path(args.probe).resolve()
    output = Path(args.out).resolve()
    journal = Path(args.journal).resolve()
    if not manifest.is_file() or not os.access(manifest, os.R_OK):
        raise MeasurementVoid(f"manifest is not readable: {manifest}")
    if not probe.is_file() or not os.access(probe, os.X_OK):
        raise MeasurementVoid(f"probe is not executable: {probe}")
    if not PREREGISTRATION.is_file():
        raise MeasurementVoid(f"preregistration is missing: {PREREGISTRATION}")
    require_clean_tree()
    admitted = admission()
    source_sha = git_sha()
    runner_sha = sha256_file(Path(__file__).resolve())
    probe_sha = sha256_file(probe)
    manifest_sha = sha256_file(manifest)
    prereg_sha = sha256_file(PREREGISTRATION)
    append_journal(
        journal,
        "started",
        source_sha=source_sha,
        runner_sha=runner_sha,
        probe_sha=probe_sha,
        manifest_sha=manifest_sha,
        preregistration_sha=prereg_sha,
        admission=admitted,
    )
    command = [str(probe), "measure", str(manifest)]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=_environment_vars(admitted, runner_sha, prereg_sha),
        capture_output=True,
        text=True,
        check=False,
        timeout=1500,
    )
    if completed.returncode != 0:
        raise MeasurementVoid(f"probe returned {completed.returncode}: {completed.stderr.strip()}")
    try:
        bundle = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise MeasurementVoid(f"probe stdout is not JSON: {error}") from error
    validate_bundle(bundle, expected_source_sha=source_sha)
    expected_provenance = {
        "runner_sha": runner_sha,
        "probe_sha": probe_sha,
        "binary_sha": probe_sha,
        "manifest_sha": manifest_sha,
        "preregistration_sha": prereg_sha,
    }
    for field, expected in expected_provenance.items():
        if bundle["provenance"][field] != expected:
            raise MeasurementVoid(f"probe provenance mismatch for {field}")
    after = admission()
    append_journal(journal, "validated", summary=bundle["summary"], admission_after=after)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if os.environ.get("CUBRIM_TELEMETRY_WRAPPED") != "1":
        affinity = sorted(os.sched_getaffinity(0))
        if len(affinity) != 1:
            env = os.environ.copy()
            env["CUBRIM_TELEMETRY_WRAPPED"] = "1"
            completed = subprocess.run(
                taskset_argv(0 if 0 in affinity else affinity[0], sys.argv[1:]),
                cwd=REPO_ROOT,
                env=env,
                check=False,
            )
            return completed.returncode
    try:
        return run(args)
    except (MeasurementVoid, OSError, subprocess.TimeoutExpired) as error:
        append_journal(Path(args.journal).resolve(), "void", reason=str(error))
        print(f"allocator telemetry VOID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
