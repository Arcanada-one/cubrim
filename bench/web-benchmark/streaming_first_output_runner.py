#!/usr/bin/env python3
"""Run and fail-closed-validate the CUBR-0075 streaming probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path


EXPECTED_SAMPLES = 13
EXPECTED_MODES = {"streaming", "whole_buffer"}
WARMUPS = 3
TRIALS = 30


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def load_temperature_c() -> list[float]:
    values: list[float] = []
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            values.append(int(path.read_text().strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    return values


def admission_snapshot() -> dict[str, object]:
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    per_cpu = load / len(affinity) if load is not None and affinity else None
    temperatures = load_temperature_c()
    return {
        "pid": os.getpid(),
        "affinity": affinity,
        "logical_cpu_count": os.cpu_count(),
        "load_1m": load,
        "load_per_affined_cpu": per_cpu,
        "temperatures_c": temperatures,
    }


def pin_to_cpu_zero() -> None:
    if not hasattr(os, "sched_setaffinity"):
        raise RuntimeError("cannot prove singleton CPU admission on this platform")
    try:
        os.sched_setaffinity(0, {0})
    except OSError as error:
        raise RuntimeError(f"cannot pin runner to CPU 0: {error}") from error


def assert_admitted(snapshot: dict[str, object], label: str) -> None:
    affinity = snapshot["affinity"]
    if not isinstance(affinity, list) or len(affinity) != 1:
        raise RuntimeError(f"{label}: expected singleton affinity, got {affinity!r}")
    per_cpu = snapshot["load_per_affined_cpu"]
    if per_cpu is not None and float(per_cpu) > 1.0:
        raise RuntimeError(f"{label}: load per affined CPU {per_cpu} > 1.0")
    temperatures = snapshot["temperatures_c"]
    if any(float(value) >= 90.0 for value in temperatures):
        raise RuntimeError(f"{label}: temperature admission failed: {temperatures!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--probe-source", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def validate_trials(bundle: dict[str, object]) -> dict[str, object]:
    if bundle.get("schema_version") != 1:
        raise RuntimeError("unexpected probe schema")
    if bundle.get("status") != "COMPLETE":
        raise RuntimeError(f"probe did not complete: {bundle.get('status')!r}")
    if bundle.get("sample_count") != EXPECTED_SAMPLES:
        raise RuntimeError("probe sample cardinality mismatch")
    if bundle.get("mode_count") != len(EXPECTED_MODES):
        raise RuntimeError("probe mode cardinality mismatch")
    provenance = bundle.get("provenance")
    if not isinstance(provenance, dict):
        raise RuntimeError("probe provenance is not an object")
    for key in (
        "source_commit",
        "probe_source_sha256",
        "probe_binary_sha256",
        "runner_sha256",
        "prereg_sha256",
        "manifest_sha256",
        "host",
        "arch",
        "cpu_affinity",
        "rustc",
    ):
        if not provenance.get(key):
            raise RuntimeError(f"probe provenance is missing {key}")
    trials = bundle.get("trials")
    if not isinstance(trials, list):
        raise RuntimeError("probe trials is not a list")

    cells: dict[tuple[str, str], list[dict[str, object]]] = {}
    for trial in trials:
        if not isinstance(trial, dict):
            raise RuntimeError("trial is not an object")
        mode = trial.get("mode")
        sample_id = trial.get("sample_id")
        if mode not in EXPECTED_MODES or not isinstance(sample_id, str):
            raise RuntimeError("trial has unknown mode or sample")
        if trial.get("status") != "valid":
            raise RuntimeError(f"invalid trial: {sample_id}/{mode}: {trial.get('error')}")
        for key in ("finish_ok", "roundtrip_exact", "sink_exact"):
            if trial.get(key) is not True:
                raise RuntimeError(f"{sample_id}/{mode}: {key} is not true")
        if not isinstance(trial.get("first_output_latency_ns"), int):
            raise RuntimeError(f"{sample_id}/{mode}: missing first-output timestamp")
        if not isinstance(trial.get("output_complete_latency_ns"), int):
            raise RuntimeError(f"{sample_id}/{mode}: missing completion timestamp")
        if trial["first_output_latency_ns"] > trial["output_complete_latency_ns"]:
            raise RuntimeError(f"{sample_id}/{mode}: output time moved backwards")
        if trial.get("first_output_input_bytes") is None:
            raise RuntimeError(f"{sample_id}/{mode}: missing first-output input count")
        if trial["first_output_input_bytes"] > trial["frame_bytes"]:
            raise RuntimeError(f"{sample_id}/{mode}: first output past frame length")
        expected_before_eof = trial["first_output_input_bytes"] < trial["frame_bytes"]
        if trial.get("first_output_before_eof") is not expected_before_eof:
            raise RuntimeError(f"{sample_id}/{mode}: first-output predicate mismatch")
        cells.setdefault((sample_id, mode), []).append(trial)

    expected_cells = EXPECTED_SAMPLES * len(EXPECTED_MODES)
    if len(cells) != expected_cells:
        raise RuntimeError(f"expected {expected_cells} cells, got {len(cells)}")
    if len({sample_id for sample_id, _mode in cells}) != EXPECTED_SAMPLES:
        raise RuntimeError("sample identity cardinality mismatch")
    for cell, rows in cells.items():
        warmups = [row for row in rows if row["warmup"]]
        measured = [row for row in rows if not row["warmup"]]
        if len(warmups) != WARMUPS or len(measured) != TRIALS:
            raise RuntimeError(f"{cell}: expected {WARMUPS}+{TRIALS}, got {len(warmups)}+{len(measured)}")
        if {row["trial_index"] for row in measured} != set(range(1, TRIALS + 1)):
            raise RuntimeError(f"{cell}: measured trial indexes are not 1..{TRIALS}")

    measured_stream = [
        row
        for (sample_id, mode), rows in cells.items()
        if mode == "streaming"
        for row in rows
        if not row["warmup"]
    ]
    measured_whole = [
        row
        for (sample_id, mode), rows in cells.items()
        if mode == "whole_buffer"
        for row in rows
        if not row["warmup"]
    ]
    if len(measured_stream) != 390 or len(measured_whole) != 390:
        raise RuntimeError("measured mode cardinality mismatch")
    first_before_eof = [row for row in measured_stream if row["first_output_before_eof"]]
    fractions = [row["first_output_input_bytes"] / row["frame_bytes"] for row in measured_stream]
    return {
        "classification": "GO" if len(first_before_eof) == len(measured_stream) else "NO_GO",
        "streaming_measured_trials": len(measured_stream),
        "streaming_first_output_before_eof_trials": len(first_before_eof),
        "streaming_first_output_before_eof_rate": len(first_before_eof) / len(measured_stream),
        "streaming_first_output_input_fraction_median": statistics.median(fractions),
        "streaming_first_output_input_fraction_max": max(fractions),
        "streaming_first_output_latency_ns_median": statistics.median(
            row["first_output_latency_ns"] for row in measured_stream
        ),
        "whole_buffer_control_trials": len(measured_whole),
        "whole_buffer_control_before_eof_trials": sum(
            1 for row in measured_whole if row["first_output_before_eof"]
        ),
    }


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    corpus_root = args.corpus_root.resolve()
    probe = args.probe.resolve()
    probe_source = args.probe_source.resolve()
    prereg = args.prereg.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if run_checked(["git", "status", "--porcelain"], repo_root):
        raise RuntimeError("working tree is dirty; commit the probe and preregistration first")

    pin_to_cpu_zero()
    before = admission_snapshot()
    assert_admitted(before, "before")
    source_commit = run_checked(["git", "rev-parse", "HEAD"], repo_root)
    rustc = run_checked(["rustc", "-Vv"], repo_root)
    env = os.environ.copy()
    env.update(
        {
            "CUBR_SOURCE_COMMIT": source_commit,
            "CUBR_PROBE_SOURCE_SHA256": sha256_path(probe_source),
            "CUBR_PROBE_BINARY_SHA256": sha256_path(probe),
            "CUBR_RUNNER_SHA256": sha256_path(Path(__file__).resolve()),
            "CUBR_PREREG_SHA256": sha256_path(prereg),
            "CUBR_HOST": platform.node(),
            "CUBR_RUSTC": rustc,
        }
    )
    command = [str(probe), str(corpus_root), str(output)]
    if shutil.which("taskset"):
        command = ["taskset", "--cpu-list", "0", *command]
    completed = subprocess.run(command, cwd=repo_root, env=env, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"probe failed with {completed.returncode}: {completed.stderr.strip()}"
        )
    bundle = json.loads(output.read_text())
    expected_provenance = {
        "source_commit": source_commit,
        "probe_source_sha256": sha256_path(probe_source),
        "probe_binary_sha256": sha256_path(probe),
        "runner_sha256": sha256_path(Path(__file__).resolve()),
        "prereg_sha256": sha256_path(prereg),
        "manifest_sha256": sha256_path(corpus_root / "manifest.v3.json"),
        "host": platform.node(),
        "arch": platform.machine().lower(),
        "cpu_affinity": str(0),
        "rustc": rustc,
    }
    for key, expected in expected_provenance.items():
        actual = bundle.get("provenance", {}).get(key)
        if actual != expected:
            raise RuntimeError(f"provenance mismatch for {key}: {actual!r} != {expected!r}")
    summary = validate_trials(bundle)
    after = admission_snapshot()
    assert_admitted(after, "after")
    bundle["admission"] = {"before": before, "after": after}
    bundle["measurement"] = summary
    bundle["measurement"]["probe_stderr"] = completed.stderr.strip()
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix="streaming-first-output-", suffix=".json", dir=output.parent
    )
    os.close(temporary_fd)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
