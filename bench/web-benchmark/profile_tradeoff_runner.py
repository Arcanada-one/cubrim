#!/usr/bin/env python3
"""Run and finalize the CUBR-0075 static/dynamic profile measurement.

The Rust probe owns codec attribution and exact round-trip checks. This wrapper
owns host admission, child-process peak RSS, bundle provenance, and the frozen
aggregate statistics. It never writes the database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from hypothesis_runner import (
    MeasurementVoid,
    _git_sha,
    _read_temperature_celsius as _read_thermal_temperature_celsius,
    _host_cpu_count,
    _cpu_topology,
    choose_cpu,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIALS = 30
WARMUPS = 3
BOOTSTRAP_ITERATIONS = 5_000
SEED = 75_075
DISCLOSURE = "LEGAL-0061:terminal-compliant"


def _read_temperature_celsius() -> list[float]:
    """Read thermal-zone sensors, falling back to hwmon on bare-metal hosts."""

    temperatures = _read_thermal_temperature_celsius()
    if temperatures:
        return temperatures
    for name_path in sorted(Path("/sys/class/hwmon").glob("hwmon*/name")):
        for temp_path in sorted(name_path.parent.glob("temp*_input")):
            try:
                temperatures.append(int(temp_path.read_text(encoding="ascii").strip()) / 1000.0)
            except (OSError, ValueError):
                continue
    return temperatures


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def append_journal(path: Path, event: str, **fields: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"event": event, "recorded_at_epoch": time.time(), **fields}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _ensure_taskset() -> int | None:
    """Re-exec this wrapper under taskset when the current mask is not singleton."""

    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) == 1:
        return None
    taskset = shutil.which("taskset")
    if taskset is None:
        raise MeasurementVoid("taskset is required to pin profile-tradeoff to one logical CPU")
    cpu = choose_cpu()
    completed = subprocess.run(
        [taskset, "--cpu-list", str(cpu), sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=REPO_ROOT,
        check=False,
    )
    return completed.returncode


def _recheck_admission(cpu: int, host_cpu_count: int) -> None:
    """Recheck the same load, affinity, and sensor sources during the run."""

    affinity = sorted(os.sched_getaffinity(0))
    load_per_cpu = os.getloadavg()[0] / host_cpu_count
    temperatures = _read_temperature_celsius()
    if affinity != [cpu] or load_per_cpu > 1.0 or not temperatures or max(temperatures) >= 90.0:
        raise MeasurementVoid(
            json.dumps(
                {
                    "reason": "admission_lapsed",
                    "effective_affinity": affinity,
                    "expected_cpu": cpu,
                    "load_per_cpu": load_per_cpu,
                    "max_temperature_c": max(temperatures) if temperatures else None,
                },
                sort_keys=True,
            )
        )


def require_clean_tree() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        raise MeasurementVoid("profile-tradeoff source tree is not clean")


def nearest_rank(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def bootstrap_median(values: list[float], seed: int) -> dict[str, float]:
    if not values:
        raise MeasurementVoid("cannot bootstrap an empty value set")
    state = seed & ((1 << 64) - 1) or 1
    medians: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample: list[float] = []
        for _ in values:
            state = (state * 6_364_136_223_846_793_005 + 1_442_695_040_888_963_407) & ((1 << 64) - 1)
            sample.append(values[(state >> 16) % len(values)])
        medians.append(nearest_rank(sample, 0.5))
    return {
        "low": nearest_rank(medians, 0.025),
        "high": nearest_rank(medians, 0.975),
    }


def admit(cpu: int) -> dict[str, Any]:
    affinity = sorted(os.sched_getaffinity(0))
    load_1m = os.getloadavg()[0]
    temperatures = _read_temperature_celsius()
    topology = _cpu_topology(cpu)
    host_cpu_count = _host_cpu_count()
    accepted = bool(
        affinity == [cpu]
        and load_1m / host_cpu_count <= 1.0
        and temperatures
        and max(temperatures) < 90.0
        and topology is not None
    )
    value = {
        "accepted": accepted,
        "load_1m": load_1m,
        "load_per_cpu": load_1m / host_cpu_count,
        "max_load_per_cpu": 1.0,
        "temperature_c": temperatures,
        "max_temperature_c": max(temperatures) if temperatures else None,
        "max_temperature_c_exclusive": 90.0,
        "process_affinity": affinity,
        "topology": topology,
        "requested_cpu": cpu,
    }
    if not accepted:
        raise MeasurementVoid(json.dumps({"reason": "failed_admission", **value}, sort_keys=True))
    return value


def run_probe(probe: Path, manifest: Path, cpu: int) -> tuple[dict[str, Any], int]:
    if not probe.is_file() or probe.is_symlink():
        raise MeasurementVoid(f"probe is not a regular file: {probe}")
    command = [str(probe), "measure", str(manifest), str(TRIALS), str(WARMUPS), str(SEED)]
    host_cpu_count = _host_cpu_count()
    process = subprocess.Popen(command, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 20 * 60
    while True:
        if time.monotonic() >= deadline:
            process.kill()
            process.wait()
            raise MeasurementVoid("profile probe exceeded the 20-minute bound")
        try:
            stdout, stderr = process.communicate(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            _recheck_admission(cpu, host_cpu_count)
    if process.returncode != 0:
        raise MeasurementVoid(f"profile probe failed with {process.returncode}: {stderr.decode(errors='replace').strip()}")
    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise MeasurementVoid(f"profile probe did not emit JSON: {error}") from error
    peak_rss = int(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024)
    return output, peak_rss


def validate_probe(output: dict[str, Any], peak_rss: int, manifest_path: Path) -> dict[str, Any]:
    if output.get("schema_version") != 1 or output.get("corpus_manifest_schema_version") != 2:
        raise MeasurementVoid("unexpected profile probe schema")
    if output.get("block_size") != 65_536 or output.get("trials_per_cell") != TRIALS or output.get("warmups") != WARMUPS:
        raise MeasurementVoid("profile probe protocol does not match the frozen preregistration")
    samples = output.get("samples")
    if not isinstance(samples, list) or len(samples) != 13:
        raise MeasurementVoid("profile probe must cover all 13 canonical v3 samples")
    sample_ids: set[str] = set()
    dynamic_trial_throughput: list[float] = []
    static_bytes = 0
    dynamic_bytes = 0
    total_input = 0
    for sample in samples:
        if not isinstance(sample, dict):
            raise MeasurementVoid("profile sample is not an object")
        sample_id = sample.get("sample_id")
        if not isinstance(sample_id, str) or sample_id in sample_ids:
            raise MeasurementVoid("profile sample IDs are not unique")
        sample_ids.add(sample_id)
        input_bytes = sample.get("input_bytes")
        input_sha = sample.get("input_sha256")
        if not isinstance(input_bytes, int) or input_bytes <= 0 or not isinstance(input_sha, str):
            raise MeasurementVoid(f"invalid input metadata for {sample_id}")
        static = sample.get("static_profile")
        dynamic = sample.get("dynamic_profile")
        if not isinstance(static, dict) or not isinstance(dynamic, dict):
            raise MeasurementVoid(f"missing profile pair for {sample_id}")
        static_frame = static.get("frame_bytes")
        dynamic_frame = dynamic.get("frame_bytes")
        if not isinstance(static_frame, int) or not isinstance(dynamic_frame, int) or static_frame <= 0 or dynamic_frame <= 0:
            raise MeasurementVoid(f"invalid frame sizes for {sample_id}")
        static_bytes += static_frame
        dynamic_bytes += dynamic_frame
        total_input += input_bytes
        for profile_name, profile in (("static", static), ("dynamic", dynamic)):
            trials = profile.get("trials")
            if not isinstance(trials, list) or len(trials) != TRIALS:
                raise MeasurementVoid(f"{sample_id}/{profile_name} does not have 30 trials")
            seen_trials: set[int] = set()
            for trial in trials:
                if not isinstance(trial, dict) or trial.get("roundtrip_exact") is not True:
                    raise MeasurementVoid(f"{sample_id}/{profile_name} failed round-trip validation")
                trial_no = trial.get("trial_no")
                encode_ns = trial.get("encode_ns")
                decode_ns = trial.get("decode_ns")
                if not isinstance(trial_no, int) or trial_no in seen_trials or not 1 <= trial_no <= TRIALS:
                    raise MeasurementVoid(f"{sample_id}/{profile_name} has invalid trial numbering")
                if not isinstance(encode_ns, int) or encode_ns <= 0 or not isinstance(decode_ns, int) or decode_ns <= 0:
                    raise MeasurementVoid(f"{sample_id}/{profile_name} has invalid timings")
                seen_trials.add(trial_no)
                # Peak RSS is a run-level observation, repeated on each resource
                # row so the guarded writer can satisfy the mandatory metric set.
                trial.setdefault("peak_memory_bytes", peak_rss)
            if len(seen_trials) != TRIALS:
                raise MeasurementVoid(f"{sample_id}/{profile_name} has incomplete trials")
    if len(sample_ids) != 13:
        raise MeasurementVoid("profile probe sample count is incomplete")
    for trial_no in range(1, TRIALS + 1):
        total_seconds = 0.0
        for sample in samples:
            total_seconds += next(t["encode_ns"] for t in sample["dynamic_profile"]["trials"] if t["trial_no"] == trial_no) / 1_000_000_000
        dynamic_trial_throughput.append(total_input / total_seconds)
    ratio_loss = dynamic_bytes / static_bytes - 1.0
    throughput_bootstrap = bootstrap_median(dynamic_trial_throughput, SEED)
    throughput_value = throughput_bootstrap["low"]
    go = throughput_value >= 50_000_000 and ratio_loss <= 0.05
    win = go and ratio_loss <= 0.02
    output["evaluation"] = {
        "aggregate_input_bytes": total_input,
        "static_frame_bytes": static_bytes,
        "dynamic_frame_bytes": dynamic_bytes,
        "dynamic_ratio_loss_vs_static": ratio_loss,
        "dynamic_compression_throughput": throughput_value,
        "dynamic_compression_throughput_point": sum(dynamic_trial_throughput) / len(dynamic_trial_throughput),
        "dynamic_compression_throughput_bootstrap_95": throughput_bootstrap,
        "decision": "WIN" if win else "GO" if go else "NO-GO",
        "criteria": {
            "go_throughput_bytes_per_second": 50_000_000,
            "go_ratio_loss": 0.05,
            "win_ratio_loss": 0.02,
        },
    }
    output["peak_memory_bytes"] = peak_rss
    output["corpus_manifest_sha256"] = sha256_file(manifest_path)
    return output


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=REPO_ROOT / "bench" / "web-corpus" / "manifest.v3.json")
    parser.add_argument("--probe", type=Path, default=REPO_ROOT / "code" / "cubrim-rs" / "target" / "release" / "examples" / "profile_tradeoff_probe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args(argv)
    journal = args.journal or args.out.with_suffix(".journal.jsonl")
    append_journal(
        journal,
        "measurement_started",
        task_id="CUBR-0075",
        phase="profile-tradeoff",
        manifest=str(args.manifest),
        probe=str(args.probe),
        output=str(args.out),
        database_write=False,
    )
    try:
        reexec = _ensure_taskset()
        if reexec is not None:
            append_journal(journal, "taskset_child_completed", return_code=reexec)
            return reexec
        require_clean_tree()
        cpu = choose_cpu()
        admission = admit(cpu)
        started = time.time()
        raw, peak_rss = run_probe(args.probe, args.manifest, cpu)
        bundle = validate_probe(raw, peak_rss, args.manifest)
        code_sha = _git_sha()
        probe_sha = sha256_file(args.probe)
        environment = {
            "hostname": platform.node(),
            "os": platform.platform(),
            "python": platform.python_version(),
            "cpu": platform.processor(),
            "affinity": sorted(os.sched_getaffinity(0)),
            "admission": admission,
        }
        bundle.update(
            {
                "task_id": "CUBR-0075",
                "phase": "profile-tradeoff",
                "scope": "profile_pair",
                "source_sha": code_sha,
                "runner_code_sha": code_sha,
                "probe_binary_sha256": probe_sha,
                "started_at_epoch": started,
                "completed_at_epoch": time.time(),
                "environment": environment,
                "publication": {"disclosure_status_reference": DISCLOSURE},
                "protocol": {
                    "warmups": WARMUPS,
                    "trials_per_cell": TRIALS,
                    "seed": SEED,
                    "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
                    "block_size": 65_536,
                    "roundtrip_gate": "decoded SHA-256 and byte equality on every trial",
                    "void_policy": "journal-only; no partial database result",
                },
                "toolchain": {
                    "probe": str(args.probe.relative_to(REPO_ROOT)),
                    "probe_binary_sha256": probe_sha,
                    "source_sha": code_sha,
                    "static_entry_point": "EncodeConfig::web_profile",
                    "dynamic_entry_point": "cubrim::encode_web_dynamic",
                },
            }
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(json.dumps(bundle, sort_keys=True, indent=2).encode() + b"\n")
        bundle_sha = sha256_file(args.out)
        append_journal(
            journal,
            "measurement_completed",
            output=str(args.out),
            bundle_sha256=bundle_sha,
            decision=bundle["evaluation"]["decision"],
            source_sha=code_sha,
            database_write=False,
        )
        print(json.dumps({"out": str(args.out), "sha256": bundle_sha, "decision": bundle["evaluation"]["decision"]}, sort_keys=True))
        return 0
    except MeasurementVoid as error:
        append_journal(
            journal,
            "measurement_void",
            reason=str(error),
            output=str(args.out),
            database_write=False,
        )
        print(f"profile-tradeoff measurement VOID: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        append_journal(
            journal,
            "measurement_error",
            error_type=type(error).__name__,
            reason=str(error),
            output=str(args.out),
            database_write=False,
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
