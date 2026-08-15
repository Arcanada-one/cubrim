#!/usr/bin/env python3
"""Measure the CUBR-0075 hostile/truncated-input contract.

The runner creates three deterministic synthetic media families at the frozen
4/8/16/32/64 KiB ladder, builds one content-addressed valid frame per sample,
and executes one contained Rust process for each warmup or measured trial.
The child performs one exact valid decode and a fixed schedule of proper
prefixes plus header mutations. ``systemd-run`` supplies the 256 MiB and 2 s
per-process ceilings; GNU ``time`` supplies peak RSS. The runner never writes
the database.

The valid p99 is measured per sample. The frozen ceilings are
``max(1 s, 4 * valid_p99 + 10 ms)`` for GO and
``max(1 s, 2 * valid_p99 + 5 ms)`` for WIN. Missing or faulted cases count as
criterion failures instead of disappearing from the aggregate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
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
    MeasurementVoid,
    _cpu_topology,
    _host_cpu_count,
    _read_temperature_celsius,
    _recheck_admission,
    _require_clean_tree,
    choose_cpu,
)


TASK_ID = "CUBR-0075"
PHASE = "hostile_truncated"
TRIALS = 30
WARMUPS = 3
SEED = 75_075
GO_MEMORY_BYTES = 268_435_456
GO_RUNTIME_NS = 1_000_000_000
WIN_RUNTIME_NS = 1_000_000_000
GO_P99_MULTIPLIER = 4
WIN_P99_MULTIPLIER = 2
GO_P99_ADD_NS = 10_000_000
WIN_P99_ADD_NS = 5_000_000
FAMILIES = ("structured_text", "structured_json", "high_entropy")
SIZES = (4 * 1024, 8 * 1024, 16 * 1024, 32 * 1024, 64 * 1024)
SAMPLE_IDS = {f"{family}-{size}" for family in FAMILIES for size in SIZES}
CASE_IDS = tuple(
    [f"prefix-{index:02}" for index in range(7)]
    + ["mutation-magic", "mutation-version", "mutation-mode"]
)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBE = REPO_ROOT / "code" / "cubrim-rs" / "target" / "release" / "examples" / "hostile_truncated_probe"
TIME_BINARY = Path("/usr/bin/time")
SYSTEMD_RUN = shutil.which("systemd-run")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    value = completed.stdout.strip()
    if len(value) not in (40, 64) or any(character not in "0123456789abcdef" for character in value):
        raise MeasurementVoid("source HEAD is not a lowercase Git SHA")
    return value


def safe_environment() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "LC_ALL": "C",
        "LANG": "C",
        "HOME": "/nonexistent",
        "SYSTEMD_COLORS": "0",
        "TERM": "dumb",
        "XDG_RUNTIME_DIR": "/run/user/1002",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1002/bus",
    }


def choose_requested_cpu(requested: int | None) -> int:
    available = sorted(os.sched_getaffinity(0))
    if not available:
        raise MeasurementVoid("no CPU is available for hostile-input measurement")
    if requested is not None:
        if requested not in available:
            raise MeasurementVoid(f"requested CPU {requested} is outside process affinity")
        return requested
    return choose_cpu()


def ensure_singleton_affinity(argv: list[str], requested: int | None) -> int | None:
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) == 1:
        if requested is not None and affinity[0] != requested:
            raise MeasurementVoid(f"runner is pinned to CPU {affinity[0]}, not requested CPU {requested}")
        return None
    if not shutil.which("taskset"):
        raise MeasurementVoid("taskset is required to pin hostile-input measurement to one CPU")
    cpu = choose_requested_cpu(requested)
    completed = subprocess.run(
        ["taskset", "--cpu-list", str(cpu), sys.executable, str(Path(__file__).resolve()), *argv],
        cwd=REPO_ROOT,
        env=safe_environment(),
        check=False,
    )
    return completed.returncode


def admit_host(cpu: int) -> dict[str, Any]:
    affinity = sorted(os.sched_getaffinity(0))
    load_1m = os.getloadavg()[0]
    host_cpu_count = _host_cpu_count()
    temperatures = _read_temperature_celsius()
    topology = _cpu_topology(cpu)
    value = {
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
    if not value["accepted"]:
        raise MeasurementVoid(json.dumps({"reason": "failed_admission", **value}, sort_keys=True))
    return value


def payload_for(family: str, size: int, seed: int) -> bytes:
    if family == "structured_text":
        template = (
            b'<article data-family="structured-text"><h2>Hostile decoder fixture</h2>'
            b'<p>deterministic structured text remains byte-addressable.</p></article>\n'
        )
        return (template * ((size + len(template) - 1) // len(template)))[:size]
    if family == "structured_json":
        document = {
            "schema": 1,
            "family": "structured-json",
            "records": [{"index": index, "kind": "web", "value": "stable"} for index in range(8)],
            "padding": "",
        }
        base = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("ascii")
        if len(base) > size:
            raise MeasurementVoid(f"JSON fixture base exceeds requested size {size}")
        document["padding"] = "x" * (size - len(base))
        payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("ascii")
        if len(payload) != size:
            raise MeasurementVoid(f"JSON fixture sizing drifted for {size}: {len(payload)}")
        return payload
    if family == "high_entropy":
        seed_bytes = (seed & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "big")
        return hashlib.shake_256(seed_bytes).digest(size)
    raise MeasurementVoid(f"unknown media family {family}")


def build_manifest(work_dir: Path, seed: int) -> dict[str, Any]:
    payload_dir = work_dir / "payloads"
    samples: list[dict[str, Any]] = []
    for family in FAMILIES:
        for size in SIZES:
            sample_id = f"{family}-{size}"
            path = payload_dir / f"{sample_id}.payload"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = payload_for(family, size, seed + size)
            path.write_bytes(payload)
            samples.append(
                {
                    "sample_id": sample_id,
                    "family": family,
                    "path": str(Path("payloads") / path.name),
                    "input_bytes": len(payload),
                    "input_sha256": sha256_bytes(payload),
                }
            )
    return {"schema_version": 1, "seed": seed, "samples": samples}


def run_json(command: list[str], *, timeout: float = 30.0) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=safe_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise MeasurementVoid(f"probe failed before evidence: exit {completed.returncode}")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise MeasurementVoid(f"probe did not emit JSON: {error}") from error
    if not isinstance(value, dict):
        raise MeasurementVoid("probe JSON is not an object")
    return value


def prepare(args: argparse.Namespace) -> None:
    _require_clean_tree()
    if not TIME_BINARY.is_file():
        raise MeasurementVoid("/usr/bin/time is required for hostile-input RSS")
    if SYSTEMD_RUN is None:
        raise MeasurementVoid("systemd-run is required for hostile-input containment")
    probe = args.probe.resolve()
    if not probe.is_file() or probe.is_symlink():
        raise MeasurementVoid(f"probe is not a regular file: {probe}")
    cpu = choose_requested_cpu(args.cpu)
    admission = admit_host(cpu)
    work_dir = args.work_dir.resolve()
    if (work_dir / "metadata.json").exists():
        raise MeasurementVoid(f"work directory already contains a prepared run: {work_dir}")
    work_dir.mkdir(parents=True, mode=0o700)
    manifest = build_manifest(work_dir, args.seed)
    manifest_path = work_dir / "manifest.json"
    write_json(manifest_path, manifest)
    prepared = run_json([str(probe), "prepare", str(manifest_path)])
    prepared_samples = prepared.get("samples")
    if prepared.get("schema_version") != 1 or not isinstance(prepared_samples, list):
        raise MeasurementVoid("probe prepared manifest has the wrong schema")
    prepared_by_id = {row.get("sample_id"): row for row in prepared_samples if isinstance(row, dict)}
    if set(prepared_by_id) != SAMPLE_IDS:
        raise MeasurementVoid("probe prepared manifest does not cover all 15 hostile samples")
    for sample in manifest["samples"]:
        row = prepared_by_id.get(sample["sample_id"])
        if not isinstance(row, dict) or row.get("input_sha256") != sample["input_sha256"] or tuple(row.get("case_ids", [])) != CASE_IDS:
            raise MeasurementVoid(f"prepared metadata drifted for {sample['sample_id']}")
    write_json(work_dir / "prepared.json", prepared)
    source_sha = git_sha()
    metadata = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "phase": PHASE,
        "source_sha": source_sha,
        "runner_sha": source_sha,
        "probe_binary": str(probe),
        "probe_binary_sha256": sha256_file(probe),
        "manifest_sha256": sha256_file(manifest_path),
        "protocol": {
            "warmups": WARMUPS,
            "trials_per_cell": TRIALS,
            "seed": args.seed,
            "cpu": cpu,
            "media_families": list(FAMILIES),
            "sizes": list(SIZES),
            "case_schedule": "7 proper prefixes plus magic/version/mode header mutations",
            "case_ids": list(CASE_IDS),
            "valid_roundtrip_gate": "decoded length and SHA-256 equal the input on every trial",
            "valid_p99": "nearest-rank p99 of the 30 valid decode durations per sample",
            "go_time_ceiling": "max(1 s, 4 * valid p99 + 10 ms)",
            "win_time_ceiling": "max(1 s, 2 * valid p99 + 5 ms)",
            "containment": {
                "systemd": "systemd-run --user --wait --collect",
                "memory_max_bytes": GO_MEMORY_BYTES,
                "runtime_max_seconds": 2,
                "private_network": True,
                "no_new_privileges": True,
                "tasks_max": 64,
            },
            "clock": "Rust Instant::now around encode/decode and each hostile case",
            "rss_measurement": "GNU time -v maximum RSS for one contained trial process",
            "measurement_scope": "valid frame and all hostile cases in one short-lived process",
            "admission_recheck": "load, temperature, and singleton affinity before every fifth trial",
        },
        "admission": admission,
        "host": {
            "hostname_sha256": sha256_bytes(socket.gethostname().encode("utf-8")),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "prepared_at": iso_now(),
    }
    write_json(work_dir / "metadata.json", metadata)
    print(json.dumps({"status": "PREPARED", "work_dir": str(work_dir), "samples": len(manifest["samples"]), "cpu": cpu}, sort_keys=True))


def parse_peak_rss(report: str) -> int:
    for line in report.splitlines():
        normalized = line.strip()
        if normalized.startswith("Maximum resident set size (kbytes):"):
            value = int(normalized.split(":", 1)[1].strip()) * 1024
            if value > 0:
                return value
    raise MeasurementVoid("GNU time report omitted maximum resident set size")


def contained_trial(
    probe: Path,
    sample: dict[str, Any],
    payload: Path,
    work_dir: Path,
    trial_no: int,
    seed: int,
) -> dict[str, Any]:
    if SYSTEMD_RUN is None:
        raise MeasurementVoid("systemd-run is required for hostile-input containment")
    with tempfile.TemporaryDirectory(prefix="hostile-trial-", dir=work_dir) as directory:
        trial_dir = Path(directory)
        report = trial_dir / "time.txt"
        command = [
            SYSTEMD_RUN,
            "--user",
            "--wait",
            "--collect",
            "--pipe",
            "--quiet",
            "--working-directory",
            str(REPO_ROOT),
            "--setenv=LC_ALL=C",
            "--setenv=LANG=C",
            "--setenv=HOME=/nonexistent",
            "--setenv=PATH=" + safe_environment()["PATH"],
            "-p",
            f"MemoryMax={GO_MEMORY_BYTES}",
            "-p",
            "RuntimeMaxSec=2s",
            "-p",
            "PrivateNetwork=yes",
            "-p",
            "NoNewPrivileges=yes",
            "-p",
            "TasksMax=64",
            "-p",
            "LimitNOFILE=1024",
            "--",
            str(TIME_BINARY),
            "--verbose",
            "--output",
            str(report),
            "--",
            str(probe),
            "trial",
            str(payload.resolve()),
            str(sample["family"]),
            str(sample["input_bytes"]),
            str(sample["input_sha256"]),
            str(sample["frame_sha256"]),
            str(sample["sample_id"]),
            str(trial_no),
            str(seed),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                env=safe_environment(),
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            return {"fault_event_count": 1, "fault_kind": "runner_timeout", "peak_rss_bytes": 0, "cases": []}
        peak_rss = 0
        if report.is_file():
            try:
                peak_rss = parse_peak_rss(report.read_text(encoding="utf-8"))
            except (OSError, ValueError, MeasurementVoid):
                peak_rss = 0
        if completed.returncode != 0:
            fault_kind = "signal" if completed.returncode < 0 else "contained_process_exit"
            return {"fault_event_count": 1, "fault_kind": fault_kind, "peak_rss_bytes": peak_rss, "cases": []}
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {"fault_event_count": 1, "fault_kind": "invalid_probe_output", "peak_rss_bytes": peak_rss, "cases": []}
        if not isinstance(value, dict):
            return {"fault_event_count": 1, "fault_kind": "invalid_probe_output", "peak_rss_bytes": peak_rss, "cases": []}
        value["peak_rss_bytes"] = peak_rss
        value["fault_event_count"] = sum(1 for case in value.get("cases", []) if isinstance(case, dict) and case.get("panic") is True)
        return value


def measure_sample(args: argparse.Namespace) -> None:
    _require_clean_tree()
    work_dir = args.work_dir.resolve()
    metadata = read_json(work_dir / "metadata.json")
    prepared = read_json(work_dir / "prepared.json")
    source_sha = git_sha()
    if metadata.get("source_sha") != source_sha:
        raise MeasurementVoid("source HEAD changed after hostile preparation")
    probe = args.probe.resolve()
    if metadata.get("probe_binary_sha256") != sha256_file(probe):
        raise MeasurementVoid("probe binary changed after hostile preparation")
    cpu = int(metadata["protocol"]["cpu"])
    admission = admit_host(cpu)
    if admission["effective_affinity"] != [cpu]:
        raise MeasurementVoid("hostile runner is not pinned to the prepared CPU")
    prepared_by_id = {row.get("sample_id"): row for row in prepared.get("samples", []) if isinstance(row, dict)}
    sample = prepared_by_id.get(args.sample_id)
    if not isinstance(sample, dict):
        raise MeasurementVoid(f"unknown hostile sample {args.sample_id}")
    result_path = (args.out.resolve() if args.out else work_dir / "results" / f"{args.sample_id}.json")
    if result_path.exists():
        raise MeasurementVoid(f"sample result already exists: {result_path}")
    payload = work_dir / str(sample["path"])
    if not payload.is_file() or payload.is_symlink():
        raise MeasurementVoid(f"sample payload is not a regular file: {payload}")
    for _ in range(WARMUPS):
        warmup = contained_trial(probe, sample, payload, work_dir, 0, int(metadata["protocol"]["seed"]))
        if warmup.get("fault_event_count", 0) or not warmup.get("valid_roundtrip_exact", False):
            raise MeasurementVoid(f"warmup containment or valid round trip failed for {args.sample_id}")
    trials: list[dict[str, Any]] = []
    for trial_no in range(1, TRIALS + 1):
        if trial_no == 1 or trial_no % 5 == 0:
            _recheck_admission(cpu, int(metadata["admission"]["available_cpu_count"]))
        value = contained_trial(probe, sample, payload, work_dir, trial_no, int(metadata["protocol"]["seed"]))
        value["trial_no"] = trial_no
        value["measured_at"] = iso_now()
        trials.append(value)
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
    if not values:
        raise MeasurementVoid("cannot rank an empty value set")
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))]


def median(values: list[float]) -> float:
    return nearest_rank(values, 0.5)


def bootstrap(values: list[float], seed: int) -> dict[str, float]:
    state = seed & ((1 << 64) - 1) or 1
    medians: list[float] = []
    for _ in range(1024):
        sample: list[float] = []
        for _ in values:
            state = (state * 6_364_136_223_846_793_005 + 1_442_695_040_888_963_407) & ((1 << 64) - 1)
            sample.append(values[(state >> 16) % len(values)])
        medians.append(median(sample))
    return {"low": nearest_rank(medians, 0.025), "high": nearest_rank(medians, 0.975)}


def aggregate(args: argparse.Namespace) -> None:
    _require_clean_tree()
    work_dir = args.work_dir.resolve()
    metadata = read_json(work_dir / "metadata.json")
    prepared = read_json(work_dir / "prepared.json")
    source_sha = git_sha()
    if metadata.get("source_sha") != source_sha:
        raise MeasurementVoid("source HEAD changed before hostile aggregation")
    prepared_samples = prepared.get("samples")
    if not isinstance(prepared_samples, list):
        raise MeasurementVoid("prepared hostile sample list is missing")
    prepared_by_id = {row.get("sample_id"): row for row in prepared_samples if isinstance(row, dict)}
    if set(prepared_by_id) != SAMPLE_IDS:
        raise MeasurementVoid("prepared hostile sample set is incomplete")
    samples: list[dict[str, Any]] = []
    total_attempts = 0
    total_errors = 0
    total_faults = 0
    total_over_go = 0
    total_over_win = 0
    peak_rss = 0
    cells: list[dict[str, Any]] = []
    for sample_id in sorted(SAMPLE_IDS):
        prepared_sample = prepared_by_id[sample_id]
        result = read_json(work_dir / "results" / f"{sample_id}.json")
        if result.get("source_sha") != source_sha:
            raise MeasurementVoid(f"{sample_id} result came from another source head")
        measured = result.get("sample")
        if not isinstance(measured, dict) or measured.get("sample_id") != sample_id:
            raise MeasurementVoid(f"{sample_id} result identity is invalid")
        trials = measured.get("trials")
        if not isinstance(trials, list) or len(trials) != TRIALS:
            raise MeasurementVoid(f"{sample_id} does not contain exactly {TRIALS} trials")
        valid_durations = [float(trial["valid_decode_ns"]) for trial in trials if trial.get("valid_roundtrip_exact") is True and isinstance(trial.get("valid_decode_ns"), int) and trial["valid_decode_ns"] > 0]
        if len(valid_durations) != TRIALS:
            raise MeasurementVoid(f"{sample_id} does not contain 30 valid exact decode timings")
        valid_p99_ns = int(nearest_rank(valid_durations, 0.99))
        go_ceiling_ns = max(GO_RUNTIME_NS, GO_P99_MULTIPLIER * valid_p99_ns + GO_P99_ADD_NS)
        win_ceiling_ns = max(WIN_RUNTIME_NS, WIN_P99_MULTIPLIER * valid_p99_ns + WIN_P99_ADD_NS)
        sample_errors = sample_faults = sample_over_go = sample_over_win = 0
        sample_peak = 0
        sample_attempts = 0
        for trial in trials:
            if trial.get("trial_no") not in range(1, TRIALS + 1):
                raise MeasurementVoid(f"{sample_id} has invalid trial numbering")
            cases = trial.get("cases")
            if not isinstance(cases, list):
                raise MeasurementVoid(f"{sample_id} cases are not a list")
            observed_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
            if trial.get("fault_event_count", 0) == 0 and tuple(sorted(observed_ids)) != tuple(sorted(CASE_IDS)):
                raise MeasurementVoid(f"{sample_id} successful trial case coverage is incomplete")
            missing = len(CASE_IDS) - len(set(observed_ids))
            errors = sum(1 for case in cases if isinstance(case, dict) and case.get("outcome") == "error")
            case_faults = sum(1 for case in cases if isinstance(case, dict) and case.get("panic") is True)
            over_go = missing + sum(1 for case in cases if isinstance(case, dict) and int(case.get("duration_ns", 0)) > go_ceiling_ns)
            over_win = missing + sum(1 for case in cases if isinstance(case, dict) and int(case.get("duration_ns", 0)) > win_ceiling_ns)
            faults = int(trial.get("fault_event_count", 0)) + case_faults
            attempts = len(CASE_IDS)
            sample_attempts += attempts
            sample_errors += errors
            sample_faults += faults
            sample_over_go += over_go
            sample_over_win += over_win
            sample_peak = max(sample_peak, int(trial.get("peak_rss_bytes", 0)))
        error_rate = sample_errors / sample_attempts
        cells.append(
            {
                "sample_id": sample_id,
                "family": measured["family"],
                "input_bytes": measured["input_bytes"],
                "frame_bytes": measured["frame_bytes"],
                "input_sha256": measured["input_sha256"],
                "frame_sha256": measured["frame_sha256"],
                "mode": prepared_sample["mode"],
                "case_count": len(CASE_IDS),
                "valid_decode_p99_ns": valid_p99_ns,
                "go_time_ceiling_ns": go_ceiling_ns,
                "win_time_ceiling_ns": win_ceiling_ns,
                "error_return_rate": error_rate,
                "fault_event_count": sample_faults,
                "over_go_time_ceiling_count": sample_over_go,
                "over_win_time_ceiling_count": sample_over_win,
                "peak_rss_bytes": sample_peak,
                "trial_count": TRIALS,
            }
        )
        total_attempts += sample_attempts
        total_errors += sample_errors
        total_faults += sample_faults
        total_over_go += sample_over_go
        total_over_win += sample_over_win
        peak_rss = max(peak_rss, sample_peak)
        samples.append({**measured, "valid_decode_p99_ns": valid_p99_ns, "go_time_ceiling_ns": go_ceiling_ns, "win_time_ceiling_ns": win_ceiling_ns})
    metrics = {
        "error_return_rate": total_errors / total_attempts,
        "fault_event_count": total_faults,
        "over_go_time_ceiling_count": total_over_go,
        "over_win_time_ceiling_count": total_over_win,
        "peak_rss_bytes": peak_rss,
    }
    go = metrics["error_return_rate"] == 1.0 and total_faults == 0 and total_over_go == 0 and peak_rss <= GO_MEMORY_BYTES
    win = go and total_over_win == 0
    decision = "WIN" if win else "GO" if go else "NO-GO"
    source_sha = str(metadata["source_sha"])
    bundle = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "phase": PHASE,
        "source_sha": source_sha,
        "runner_sha": source_sha,
        "probe_binary": metadata["probe_binary"],
        "probe_binary_sha256": metadata["probe_binary_sha256"],
        "manifest": {"schema_version": 1, "seed": metadata["protocol"]["seed"], "sha256": metadata["manifest_sha256"], "samples": [{key: sample[key] for key in ("sample_id", "family", "path", "input_bytes", "input_sha256")} for sample in [prepared_by_id[sample_id] for sample_id in sorted(SAMPLE_IDS)]]},
        "protocol": metadata["protocol"],
        "admission": metadata["admission"],
        "host": metadata["host"],
        "samples": samples,
        "evaluation": {
            "cells": cells,
            "metrics": metrics,
            "totals": {"sample_count": len(samples), "trial_count": len(samples) * TRIALS, "case_count": total_attempts},
            "decision": decision,
            "criteria": {"go_peak_rss_bytes": GO_MEMORY_BYTES, "go_error_return_rate": 1.0, "go_fault_event_count": 0, "go_over_time_count": 0, "win_over_time_count": 0},
        },
        "publication": {"state": "staged", "disclosure_status_reference": os.environ.get("CUBRIM_DISCLOSURE_STATUS_REFERENCE", "LEGAL-0061:terminal-compliant"), "database_write": False},
        "prepared_at": metadata["prepared_at"],
        "completed_at": iso_now(),
    }
    write_json(args.out.resolve(), bundle)
    print(json.dumps({"status": "PASS", "out": str(args.out.resolve()), "samples": len(samples), "trials": len(samples) * TRIALS, "cases": total_attempts, **metrics, "decision": decision}, sort_keys=True))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
