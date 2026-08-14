#!/usr/bin/env python3
"""Run and evaluate the dependency-free CUBR-0075 Phase-A ladders.

This runner is deliberately separate from ``run.py``.  The resource runner
times a subprocess protocol over a fixed corpus; these hypotheses need the
decoder call itself across deterministic cube and raw-store size ladders.
The Rust ``hypothesis_probe`` keeps the clock in-process and performs an exact
round-trip check for every measured trial.

The measurement command is intentionally fail-closed:

    python3 hypothesis_runner.py --phase-a --check

It requires a quiet, temperature-admitted single-CPU host, exactly three
warmups, and at least thirty randomized trials per cell.  It writes a
content-addressed raw bundle plus derived median/bootstrap/linearity results;
it does not write the database or assign a publication lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from statistics import median
from typing import Any, Iterable


CUBE_SIZES = (4 * 1024, 8 * 1024, 16 * 1024, 32 * 1024, 64 * 1024)
RAW_SIZES = tuple(1 << power for power in range(20, 28))
PHASE_A_TRIALS = 30
PHASE_A_WARMUPS = 3
BOOTSTRAP_ITERATIONS = 5_000
BOOTSTRAP_CONFIDENCE = 0.95
DEFAULT_SEED = 74_075
DEFAULT_CPU = None
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBE = REPO_ROOT / "code" / "cubrim-rs" / "target" / "release" / "examples" / "hypothesis_probe"


class MeasurementVoid(RuntimeError):
    """Raised when the host or a trial cannot support admissible evidence."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_temperature_celsius() -> list[float]:
    temperatures: list[float] = []
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            temperatures.append(int(path.read_text(encoding="ascii").strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    return temperatures


def _cpu_topology(cpu: int) -> dict[str, int] | None:
    base = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
    try:
        return {
            "package": int((base / "physical_package_id").read_text().strip()),
            "core": int((base / "core_id").read_text().strip()),
        }
    except (OSError, ValueError):
        return None


def _host_cpu_count() -> int:
    """Return the host CPU count used for load admission, not taskset's mask."""

    count = os.cpu_count()
    if count is None or count < 1:
        raise MeasurementVoid("cannot determine the host CPU count")
    return count


def choose_cpu(requested: int | None = DEFAULT_CPU) -> int:
    available = sorted(os.sched_getaffinity(0))
    if not available:
        raise MeasurementVoid("no CPU is available to the benchmark process")
    if requested is not None:
        if requested not in available:
            raise MeasurementVoid(f"requested CPU {requested} is outside the process affinity")
        return requested
    for cpu in available:
        if _cpu_topology(cpu) is not None:
            return cpu
    raise MeasurementVoid("cannot prove physical CPU topology for an admitted run")


def admit_host(cpu: int) -> dict[str, Any]:
    """Admit a taskset-pinned process; unknown temperature is a void."""

    affinity = sorted(os.sched_getaffinity(0))
    load_1m = os.getloadavg()[0]
    host_cpu_count = _host_cpu_count()
    load_per_cpu = load_1m / host_cpu_count
    temperatures = _read_temperature_celsius()
    topology = _cpu_topology(cpu)
    admission = {
        "accepted": bool(
            len(affinity) == 1
            and load_per_cpu <= 1.0
            and temperatures
            and max(temperatures) < 90.0
            and topology is not None
        ),
        "load_1m": load_1m,
        "available_cpu_count": host_cpu_count,
        "process_affinity": affinity,
        "load_per_cpu": load_per_cpu,
        "max_temperature_c": max(temperatures) if temperatures else None,
        "temperature_sample_count": len(temperatures),
        "max_load_per_cpu": 1.0,
        "max_temperature_c_exclusive": 90.0,
        "requested_cpu": cpu,
        "topology": topology,
    }
    if not admission["accepted"]:
        raise MeasurementVoid(json.dumps({"reason": "failed_admission", **admission}, sort_keys=True))
    admission["effective_affinity"] = sorted(os.sched_getaffinity(0))
    admission["taskset_required"] = True
    return admission


def _recheck_admission(cpu: int, host_cpu_count: int) -> None:
    affinity = sorted(os.sched_getaffinity(0))
    load_per_cpu = os.getloadavg()[0] / host_cpu_count
    temperatures = _read_temperature_celsius()
    if (
        affinity != [cpu]
        or load_per_cpu > 1.0
        or not temperatures
        or max(temperatures) >= 90.0
    ):
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


def _ensure_taskset() -> int | None:
    """Re-exec under taskset when the operator did not provide a singleton mask."""

    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) == 1:
        return None
    taskset = shutil.which("taskset")
    if taskset is None:
        raise MeasurementVoid("taskset is required to pin Phase A to one logical CPU")
    cpu = choose_cpu()
    completed = subprocess.run(
        [taskset, "--cpu-list", str(cpu), sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=REPO_ROOT,
        check=False,
    )
    return completed.returncode


def _xorshift_bytes(size: int, seed: int) -> bytes:
    state = seed & 0xFFFFFFFFFFFFFFFF
    output = bytearray(size)
    for index in range(size):
        state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
        state ^= state >> 7
        state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
        output[index] = (state >> 24) & 0xFF
    return bytes(output)


def write_payload(path: Path, size: int, kind: str, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "cube":
        template = (
            b'<article class="card card-000"><h2>WebCodec hypothesis ladder</h2>'
            b'<p>deterministic structured payload for cube-mode decode timing</p></article>\n'
        )
        payload = (template * ((size + len(template) - 1) // len(template)))[:size]
        path.write_bytes(payload)
        return
    if kind != "raw_store":
        raise ValueError(f"unknown payload kind: {kind}")
    with path.open("wb") as handle:
        remaining = size
        offset = 0
        while remaining:
            chunk_size = min(1024 * 1024, remaining)
            handle.write(_xorshift_bytes(chunk_size, seed + offset))
            remaining -= chunk_size
            offset += chunk_size


def build_manifest(directory: Path, seed: int) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for kind, sizes in (("cube", CUBE_SIZES), ("raw_store", RAW_SIZES)):
        for size in sizes:
            sample_id = f"{kind.replace('_', '-')}-{size}"
            path = directory / f"{sample_id}.payload"
            write_payload(path, size, kind, seed + size)
            samples.append(
                {
                    "sample_id": sample_id,
                    "path": str(path),
                    "expected_mode": kind,
                    "ladder": kind,
                    "input_bytes": size,
                    "input_sha256": sha256_file(path),
                }
            )
    return {"schema_version": 1, "seed": seed, "samples": samples}


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _require_clean_tree() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise MeasurementVoid("source tree is dirty; build and measure a committed exact head")


def run_probe(
    probe: Path,
    manifest_path: Path,
    trials: int,
    warmups: int,
    seed: int,
    cpu: int,
    host_cpu_count: int,
) -> dict[str, Any]:
    if not probe.is_file() or probe.is_symlink():
        raise MeasurementVoid(f"probe binary is missing or non-regular: {probe}")
    command = [str(probe), "measure", str(manifest_path), str(trials), str(warmups), str(seed)]
    deadline = time.monotonic() + 60 * 30
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=REPO_ROOT, stdout=stdout, stderr=stderr)
        try:
            while True:
                if time.monotonic() >= deadline:
                    raise MeasurementVoid("hypothesis probe exceeded the 30-minute bound")
                try:
                    returncode = process.wait(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    _recheck_admission(cpu, host_cpu_count)
        except (MeasurementVoid, subprocess.SubprocessError):
            process.kill()
            process.wait()
            raise
        stdout.seek(0)
        stderr.seek(0)
        stdout_text = stdout.read().decode("utf-8")
        stderr_text = stderr.read().decode("utf-8", errors="replace")
    if returncode != 0:
        raise MeasurementVoid(
            f"hypothesis probe failed with {returncode}: {stderr_text.strip()}"
        )
    try:
        return json.loads(stdout_text)
    except json.JSONDecodeError as error:
        raise MeasurementVoid(f"probe did not emit JSON: {error}") from error


def _nearest_rank(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile of an empty list")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def bootstrap_median(
    values: Iterable[float],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = DEFAULT_SEED,
) -> dict[str, float]:
    observations = list(values)
    if not observations or iterations < 1:
        raise ValueError("bootstrap requires observations and positive iterations")
    rng = random.Random(seed)
    resampled = [
        median(rng.choice(observations) for _ in observations)
        for _ in range(iterations)
    ]
    return {
        "median": float(median(observations)),
        "low": _nearest_rank(resampled, 0.025),
        "high": _nearest_rank(resampled, 0.975),
    }


def loglog_fit(points: Iterable[tuple[int, float]]) -> dict[str, float]:
    observations = [(math.log(size), math.log(value)) for size, value in points if size > 0 and value > 0]
    if len(observations) < 2:
        raise ValueError("log-log fit requires at least two positive points")
    x_bar = sum(x for x, _ in observations) / len(observations)
    y_bar = sum(y for _, y in observations) / len(observations)
    denominator = sum((x - x_bar) ** 2 for x, _ in observations)
    if denominator == 0:
        raise ValueError("log-log fit has no size variance")
    slope = sum((x - x_bar) * (y - y_bar) for x, y in observations) / denominator
    intercept = y_bar - slope * x_bar
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in observations)
    total = sum((y - y_bar) ** 2 for _, y in observations)
    r_squared = 1.0 if total == 0 else 1.0 - residual / total
    return {"slope_alpha": slope, "r_squared": r_squared, "point_count": len(observations)}


def _linearity_decision(fit: dict[str, float], ladder: str) -> str:
    if ladder == "cube":
        win_alpha, go_alpha, win_r2, go_r2 = 1.03, 1.10, 0.995, 0.98
    else:
        win_alpha, go_alpha, win_r2, go_r2 = 1.02, 1.05, 0.999, 0.995
    alpha = fit["slope_alpha"]
    r_squared = fit["r_squared"]
    if abs(alpha - 1.0) <= (win_alpha - 1.0) and r_squared >= win_r2:
        return "WIN"
    if abs(alpha - 1.0) <= (go_alpha - 1.0) and r_squared >= go_r2:
        return "GO"
    return "NO-GO"


def evaluate_probe(
    probe_output: dict[str, Any],
    *,
    bootstrap_iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    trials_per_cell = probe_output.get("trials_per_cell")
    if trials_per_cell is None or trials_per_cell < PHASE_A_TRIALS:
        raise MeasurementVoid("probe output has fewer than 30 trials per cell")
    cells: list[dict[str, Any]] = []
    by_ladder: dict[str, list[dict[str, Any]]] = {"cube": [], "raw_store": []}
    for sample in probe_output.get("samples", []):
        trials = sample.get("trials", [])
        if sample.get("mode") != sample.get("expected_mode"):
            raise MeasurementVoid(f"mode attribution mismatch: {sample.get('sample_id')}")
        if not sample.get("encoder_path"):
            raise MeasurementVoid(f"missing encoder path: {sample.get('sample_id')}")
        if len(trials) != trials_per_cell or not all(t.get("roundtrip_exact") is True for t in trials):
            raise MeasurementVoid(f"incomplete or non-exact cell: {sample.get('sample_id')}")
        throughputs = [sample["input_bytes"] / (t["decode_ns"] / 1_000_000_000) for t in trials]
        decode_ns = [float(t["decode_ns"]) for t in trials]
        cell = {
            "sample_id": sample["sample_id"],
            "ladder": "cube" if sample["expected_mode"] == "cube" else "raw_store",
            "mode": sample["mode"],
            "input_bytes": sample["input_bytes"],
            "frame_bytes": sample["frame_bytes"],
            "input_sha256": sample["input_sha256"],
            "frame_sha256": sample["frame_sha256"],
            "encoder_path": sample["encoder_path"],
            "decode_ns": bootstrap_median(decode_ns, iterations=bootstrap_iterations, seed=seed),
            "throughput_bytes_per_second": bootstrap_median(
                throughputs, iterations=bootstrap_iterations, seed=seed + 1
            ),
            "trial_count": len(trials),
        }
        cells.append(cell)
        by_ladder[cell["ladder"]].append(cell)

    derived: dict[str, Any] = {}
    for ladder, ladder_cells in by_ladder.items():
        if not ladder_cells:
            raise MeasurementVoid(f"missing {ladder} ladder")
        fit = loglog_fit(
            [(cell["input_bytes"], cell["decode_ns"]["median"]) for cell in ladder_cells]
        )
        derived[f"{ladder}-linearity"] = {
            "ladder_key": ladder,
            **fit,
            "decision": _linearity_decision(fit, ladder),
            "complete": True,
        }

    cube_64k = next(
        (cell for cell in by_ladder["cube"] if cell["input_bytes"] == 64 * 1024), None
    )
    if cube_64k is None:
        raise MeasurementVoid("cube ladder is missing the 64 KiB throughput cell")
    ci_low = cube_64k["throughput_bytes_per_second"]["low"]
    derived["cube-throughput"] = {
        "ladder_key": "cube",
        "sample_id": cube_64k["sample_id"],
        "input_bytes": cube_64k["input_bytes"],
        "decode_throughput_ci_low": ci_low,
        "decision": "WIN" if ci_low >= 500_000_000 else "GO" if ci_low >= 200_000_000 else "NO-GO",
        "complete": True,
    }
    return {"cells": cells, "derived": derived}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run_phase_a(args: argparse.Namespace) -> dict[str, Any]:
    if args.trials < PHASE_A_TRIALS or args.warmups != PHASE_A_WARMUPS:
        raise MeasurementVoid("Phase A requires at least 30 trials and exactly 3 warmups")
    probe = args.probe.resolve()
    _require_clean_tree()
    cpu = choose_cpu(args.cpu)
    admission = admit_host(cpu)
    source_sha = _git_sha()
    with tempfile.TemporaryDirectory(prefix="cubr-0075-phase-a-") as temporary:
        directory = Path(temporary)
        manifest = build_manifest(directory, args.seed)
        manifest_path = directory / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        probe_output = run_probe(
            probe,
            manifest_path,
            args.trials,
            args.warmups,
            args.seed,
            cpu=cpu,
            host_cpu_count=admission["available_cpu_count"],
        )
    evaluation = evaluate_probe(
        probe_output,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    result = {
        "schema_version": 1,
        "task_id": "CUBR-0075",
        "phase": "A",
        "codec_key": "cubrim-file-v1",
        "source_sha": source_sha,
        "probe_binary": str(probe),
        "probe_binary_sha256": sha256_file(probe),
        "protocol": {
            "warmups": args.warmups,
            "trials_per_cell": args.trials,
            "bootstrap_iterations": args.bootstrap_iterations,
            "bootstrap_confidence": BOOTSTRAP_CONFIDENCE,
            "seed": args.seed,
            "admission": admission,
            "host": {"platform": platform.platform(), "python": platform.python_version()},
            "roundtrip_gate": "sha256 and byte equality on every trial",
            "clock": "in-process cubrim::decode Instant::now",
            "taskset": {
                "required": True,
                "effective_affinity": admission["effective_affinity"],
                "cpu": cpu,
            },
            "admission_recheck": "parent polls load, temperature, and singleton affinity while probe runs",
        },
        "probe": probe_output,
        "evaluation": evaluation,
        "publication": {
            "state": "staged",
            "disclosure_status_reference": "LEGAL-0061:terminal-compliant",
            "database_write": False,
        },
    }
    _write_json(args.out, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-a", action="store_true", required=True)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "out" / "hypothesis-phase-a.json")
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--cpu", type=int, default=DEFAULT_CPU)
    parser.add_argument("--trials", type=int, default=PHASE_A_TRIALS)
    parser.add_argument("--warmups", type=int, default=PHASE_A_WARMUPS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--bootstrap-iterations", type=int, default=BOOTSTRAP_ITERATIONS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        reexec_returncode = _ensure_taskset()
    except (MeasurementVoid, OSError, subprocess.SubprocessError, ValueError) as error:
        print(json.dumps({"status": "VOID", "reason": str(error)}, sort_keys=True))
        return 2
    if reexec_returncode is not None:
        return reexec_returncode
    try:
        result = run_phase_a(args)
    except (MeasurementVoid, OSError, subprocess.SubprocessError, ValueError) as error:
        print(json.dumps({"status": "VOID", "reason": str(error)}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "out": str(args.out),
                "cells": len(result["evaluation"]["cells"]),
                "derived": result["evaluation"]["derived"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
