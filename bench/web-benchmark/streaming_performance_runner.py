#!/usr/bin/env python3
"""Run and fail-closed-validate the CUBR-0075 streaming performance probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


EXPECTED_SAMPLES = 13
EXPECTED_MODES = {"streaming", "whole_buffer"}
WARMUPS = 3
TRIALS = 30
BLOCK_SIZE = 65_536
CHUNK_SIZE = 4_096
SEED = 75_075
FIRST_OUTPUT_LIMIT = 65_536
AUXILIARY_RATIO_LIMIT = 1.0


class MeasurementVoid(RuntimeError):
    """The evidence cannot support a threshold result."""


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
    logical_cpu_count = os.cpu_count()
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    per_cpu = load / logical_cpu_count if load is not None and logical_cpu_count else None
    return {
        "pid": os.getpid(),
        "affinity": affinity,
        "logical_cpu_count": logical_cpu_count,
        "load_1m": load,
        "load_per_logical_cpu": per_cpu,
        "temperatures_c": load_temperature_c(),
    }


def pin_to_cpu_zero() -> None:
    if not hasattr(os, "sched_setaffinity"):
        raise MeasurementVoid("cannot prove singleton CPU admission on this platform")
    try:
        os.sched_setaffinity(0, {0})
    except OSError as error:
        raise MeasurementVoid(f"cannot pin runner to CPU 0: {error}") from error


def assert_admitted(snapshot: dict[str, object], label: str) -> None:
    affinity = snapshot["affinity"]
    if not isinstance(affinity, list) or len(affinity) != 1:
        raise MeasurementVoid(f"{label}: expected singleton affinity, got {affinity!r}")
    per_cpu = snapshot["load_per_logical_cpu"]
    if per_cpu is not None and float(per_cpu) > 1.0:
        raise MeasurementVoid(f"{label}: load per logical CPU {per_cpu} > 1.0")
    temperatures = snapshot["temperatures_c"]
    if any(float(value) >= 90.0 for value in temperatures):
        raise MeasurementVoid(f"{label}: temperature admission failed: {temperatures!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--probe-source", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--augment-from",
        type=Path,
        help="augment an existing complete decoder bundle with fresh encode timing",
    )
    return parser.parse_args()


def fail(message: str) -> None:
    raise MeasurementVoid(message)


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        fail(f"{label} is not finite numeric data")
    return float(value)


def validate_bundle(bundle: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("schema_version") != 1 or bundle.get("task_id") != "CUBR-0075":
        fail("unexpected bundle schema or task")
    if bundle.get("phase") != "streaming_performance" or bundle.get("status") != "COMPLETE":
        fail(f"probe status is not a complete measurement: {bundle.get('status')!r}")
    protocol = bundle.get("protocol")
    if protocol != {
        "samples": EXPECTED_SAMPLES,
        "modes": 2,
        "warmups": WARMUPS,
        "trials": TRIALS,
        "seed": SEED,
        "block_size": BLOCK_SIZE,
        "input_chunk_size": CHUNK_SIZE,
    }:
        fail("protocol differs from the frozen preregistration")
    manifest_samples = manifest.get("samples")
    if not isinstance(manifest_samples, list) or len(manifest_samples) != EXPECTED_SAMPLES:
        fail("canonical manifest does not contain exactly 13 samples")
    canonical = {row["sample_id"]: row for row in manifest_samples}
    samples = bundle.get("samples")
    if not isinstance(samples, list) or len(samples) != EXPECTED_SAMPLES:
        fail("bundle sample cardinality mismatch")
    sample_by_id: dict[str, dict[str, Any]] = {}
    for sample in samples:
        if not isinstance(sample, dict):
            fail("sample metadata is not an object")
        sample_id = sample.get("sample_id")
        expected = canonical.get(sample_id)
        if expected is None or sample_id in sample_by_id:
            fail(f"sample identity is not canonical: {sample_id!r}")
        for key in ("path", "byte_count", "sha256"):
            if sample.get(key) != expected.get(key):
                fail(f"{sample_id}: {key} differs from the canonical manifest")
        if not isinstance(sample.get("frame_bytes"), int) or sample["frame_bytes"] <= 0:
            fail(f"{sample_id}: frame_bytes is invalid")
        if not isinstance(sample.get("frame_sha256"), str) or len(sample["frame_sha256"]) != 64:
            fail(f"{sample_id}: frame_sha256 is invalid")
        sample_by_id[sample_id] = sample
    if set(sample_by_id) != set(canonical):
        fail("bundle does not cover the canonical sample set")

    provenance = bundle.get("provenance")
    if not isinstance(provenance, dict):
        fail("provenance is not an object")
    for key in ("source_commit", "probe_source_sha256", "probe_binary_sha256", "runner_sha256", "prereg_sha256", "manifest_sha256", "host", "arch", "cpu_affinity", "rustc"):
        if not provenance.get(key):
            fail(f"provenance is missing {key}")

    independent = bundle.get("independent_block_probe")
    if not isinstance(independent, dict) or independent.get("success") is not False:
        fail("independent-block capability must be an explicit false observation for this slice")
    if not isinstance(independent.get("evidence"), str) or not independent["evidence"].strip():
        fail("independent-block probe lacks evidence text")
    if independent.get("positive_control") is not True or independent.get("negative_control") is not True:
        fail("independent-block probe controls are incomplete")

    trials = bundle.get("trials")
    if not isinstance(trials, list):
        fail("trial collection is not a list")
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trial in trials:
        if not isinstance(trial, dict):
            fail("trial is not an object")
        sample_id = trial.get("sample_id")
        mode = trial.get("mode")
        sample = sample_by_id.get(sample_id)
        if sample is None or mode not in EXPECTED_MODES:
            fail(f"trial has unknown sample or mode: {sample_id!r}/{mode!r}")
        if trial.get("status") != "valid":
            fail(f"invalid trial: {sample_id}/{mode}: {trial.get('error')}")
        if trial.get("frame_bytes") != sample["frame_bytes"] or trial.get("input_bytes") != sample["byte_count"]:
            fail(f"{sample_id}/{mode}: frame or input size drift")
        for key in ("finish_ok", "roundtrip_exact", "sink_exact"):
            if trial.get(key) is not True:
                fail(f"{sample_id}/{mode}: {key} is not true")
        if not isinstance(trial.get("first_output_input_bytes"), int) or trial["first_output_input_bytes"] > trial["frame_bytes"]:
            fail(f"{sample_id}/{mode}: first output input position is invalid")
        expected_before_eof = trial["first_output_input_bytes"] < trial["frame_bytes"]
        if trial.get("first_output_before_eof") is not expected_before_eof:
            fail(f"{sample_id}/{mode}: pre-EOF predicate mismatch")
        for key in ("first_output_latency_ns", "last_input_latency_ns", "output_complete_latency_ns"):
            if not isinstance(trial.get(key), int) or trial[key] < 0:
                fail(f"{sample_id}/{mode}: {key} is invalid")
        if not isinstance(trial.get("compression_duration_ns"), int) or trial["compression_duration_ns"] <= 0:
            fail(f"{sample_id}/{mode}: compression_duration_ns is invalid")
        if trial["first_output_latency_ns"] > trial["last_input_latency_ns"] or trial["last_input_latency_ns"] > trial["output_complete_latency_ns"]:
            fail(f"{sample_id}/{mode}: event timestamps are not ordered")
        if mode == "streaming":
            for key in ("declared_output_bytes", "decoder_retained_peak_bytes", "auxiliary_peak_bytes"):
                if not isinstance(trial.get(key), int) or trial[key] < 0:
                    fail(f"{sample_id}/{mode}: {key} is invalid")
            expected_auxiliary = trial["decoder_retained_peak_bytes"] - trial["frame_bytes"] - trial["declared_output_bytes"]
            if expected_auxiliary < 0 or trial["auxiliary_peak_bytes"] != expected_auxiliary:
                fail(f"{sample_id}/{mode}: auxiliary-capacity subtraction is invalid")
            ratio = finite_number(trial.get("auxiliary_memory_bound_ratio"), f"{sample_id}/{mode} ratio")
            if not math.isclose(ratio, expected_auxiliary / trial["frame_bytes"], rel_tol=1e-12, abs_tol=1e-12):
                fail(f"{sample_id}/{mode}: auxiliary ratio is not derived from raw values")
        cells.setdefault((sample_id, mode), []).append(trial)

    expected_cells = EXPECTED_SAMPLES * len(EXPECTED_MODES)
    if len(cells) != expected_cells or len(trials) != expected_cells * (WARMUPS + TRIALS):
        fail("trial cardinality is incomplete")
    measured_stream: list[dict[str, Any]] = []
    measured_control: list[dict[str, Any]] = []
    for cell, rows in cells.items():
        warmups = [row for row in rows if row.get("warmup") is True]
        measured = [row for row in rows if row.get("warmup") is False]
        if len(warmups) != WARMUPS or len(measured) != TRIALS:
            fail(f"{cell}: expected {WARMUPS}+{TRIALS} trials")
        if {row.get("trial_index") for row in measured} != set(range(1, TRIALS + 1)):
            fail(f"{cell}: measured trial indexes are not 1..30")
        (measured_stream if cell[1] == "streaming" else measured_control).extend(measured)
    if len(measured_stream) != 390 or len(measured_control) != 390:
        fail("measured mode cardinality mismatch")

    max_first_output = max(row["first_output_input_bytes"] for row in measured_stream)
    max_ratio = max(finite_number(row["auxiliary_memory_bound_ratio"], "auxiliary ratio") for row in measured_stream)
    numeric_go = max_first_output <= FIRST_OUTPUT_LIMIT and max_ratio <= AUXILIARY_RATIO_LIMIT
    decision = "GO" if numeric_go and independent["success"] else "NO_GO"
    measurement = {
        "streaming_measured_trials": len(measured_stream),
        "whole_buffer_control_trials": len(measured_control),
        "max_first_output_after_input_bytes": max_first_output,
        "max_auxiliary_memory_bound_ratio": max_ratio,
        "go_first_output_after_input_bytes": max_first_output <= FIRST_OUTPUT_LIMIT,
        "go_auxiliary_memory_bound_ratio": max_ratio <= AUXILIARY_RATIO_LIMIT,
        "independent_block_decode_success": independent["success"],
        "decision": decision,
    }
    supplied = bundle.get("measurement")
    if supplied is not None and supplied != measurement:
        fail("measurement summary does not equal the raw trials")
    return measurement


def write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix="streaming-performance-", suffix=".json", dir=path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def augment_bundle(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    corpus_root = args.corpus_root.resolve()
    probe = args.probe.resolve()
    probe_source = args.probe_source.resolve()
    prereg = args.prereg.resolve()
    output = args.output.resolve()
    base_path = args.augment_from.resolve()
    if base_path == output:
        fail("augmentation input and output must be different files")
    if not base_path.is_file():
        fail(f"augmentation input does not exist: {base_path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if run_checked(["git", "status", "--porcelain"], repo_root):
        raise MeasurementVoid("working tree is dirty; commit the probe and preregistration first")

    pin_to_cpu_zero()
    before = admission_snapshot()
    assert_admitted(before, "before")
    source_commit = run_checked(["git", "rev-parse", "HEAD"], repo_root)
    rustc = run_checked(["rustc", "-Vv"], repo_root)
    manifest_path = corpus_root / "manifest.v3.json"
    manifest = json.loads(manifest_path.read_text())
    timing_fd, timing_name = tempfile.mkstemp(prefix="compression-timings-", suffix=".json", dir=output.parent)
    os.close(timing_fd)
    timing_path = Path(timing_name)
    command = [str(probe), "--compression-timings", str(corpus_root), str(timing_path)]
    if shutil.which("taskset"):
        command = ["taskset", "--cpu-list", "0", *command]
    try:
        completed = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)
        if completed.returncode != 0:
            raise MeasurementVoid(f"compression timing probe failed with {completed.returncode}: {completed.stderr.strip()}")
        try:
            timing_run = json.loads(timing_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise MeasurementVoid(f"compression timing probe did not produce JSON: {error}") from error
    finally:
        timing_path.unlink(missing_ok=True)

    if timing_run.get("schema_version") != 1 or timing_run.get("task_id") != "CUBR-0075":
        fail("unexpected compression timing schema or task")
    if timing_run.get("phase") != "compression_timing_augmentation" or timing_run.get("status") != "COMPLETE":
        fail("compression timing probe is not complete")
    timing_samples = timing_run.get("samples")
    if not isinstance(timing_samples, list) or len(timing_samples) != EXPECTED_SAMPLES:
        fail("compression timing sample cardinality mismatch")
    canonical = {row["sample_id"]: row for row in manifest.get("samples", [])}
    timings: dict[str, int] = {}
    for sample in timing_samples:
        if not isinstance(sample, dict):
            fail("compression timing sample is not an object")
        sample_id = sample.get("sample_id")
        expected = canonical.get(sample_id)
        if expected is None or sample_id in timings:
            fail(f"compression timing sample identity is not canonical: {sample_id!r}")
        for key in ("sample_path", "input_bytes", "input_sha256"):
            expected_key = "path" if key == "sample_path" else ("byte_count" if key == "input_bytes" else "sha256")
            if sample.get(key) != expected.get(expected_key):
                fail(f"{sample_id}: compression timing {key} differs from manifest")
        duration = sample.get("compression_duration_ns")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
            fail(f"{sample_id}: compression duration is invalid")
        timings[sample_id] = duration
    if set(timings) != set(canonical):
        fail("compression timing probe does not cover the canonical sample set")

    try:
        bundle = json.loads(base_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise MeasurementVoid(f"cannot read augmentation input: {error}") from error
    trials = bundle.get("trials")
    if not isinstance(trials, list):
        fail("augmentation input trial collection is not a list")
    for trial in trials:
        if not isinstance(trial, dict):
            fail("augmentation input trial is not an object")
        sample_id = trial.get("sample_id")
        if sample_id not in timings:
            fail(f"augmentation input has unknown sample: {sample_id!r}")
        if "compression_duration_ns" in trial:
            fail("augmentation input already contains compression_duration_ns")
        trial["compression_duration_ns"] = timings[sample_id]

    after = admission_snapshot()
    assert_admitted(after, "after")
    bundle["provenance"] = {
        "source_commit": source_commit,
        "probe_source_sha256": sha256_path(probe_source),
        "probe_binary_sha256": sha256_path(probe),
        "runner_sha256": sha256_path(Path(__file__).resolve()),
        "prereg_sha256": sha256_path(prereg),
        "manifest_sha256": sha256_path(manifest_path),
        "host": platform.node(),
        "arch": platform.machine().lower(),
        "cpu_affinity": "0",
        "rustc": rustc,
    }
    bundle["publication_augmentation"] = {
        "kind": "source-derived-compression-timing",
        "base_bundle_sha256": sha256_path(base_path),
        "raw_decoder_observations_unchanged": True,
        "timed_encodes_per_sample": 1,
        "timing_probe_phase": timing_run["phase"],
    }
    bundle["admission"] = {"before": before, "after": after}
    # The base runner appends probe_stderr after validating its canonical
    # measurement summary. Replace that derived field before revalidation so
    # an old diagnostic key cannot masquerade as changed raw evidence.
    bundle.pop("measurement", None)
    bundle["measurement"] = validate_bundle(bundle, manifest)
    bundle["measurement"]["probe_stderr"] = completed.stderr.strip()
    write_json_atomically(output, bundle)
    print(json.dumps(bundle["measurement"], sort_keys=True))
    return 0


def main() -> int:
    args = parse_args()
    if args.augment_from is not None:
        return augment_bundle(args)
    repo_root = args.repo_root.resolve()
    corpus_root = args.corpus_root.resolve()
    probe = args.probe.resolve()
    probe_source = args.probe_source.resolve()
    prereg = args.prereg.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if run_checked(["git", "status", "--porcelain"], repo_root):
        raise MeasurementVoid("working tree is dirty; commit the probe and preregistration first")
    pin_to_cpu_zero()
    before = admission_snapshot()
    assert_admitted(before, "before")
    source_commit = run_checked(["git", "rev-parse", "HEAD"], repo_root)
    rustc = run_checked(["rustc", "-Vv"], repo_root)
    env = os.environ.copy()
    env.update({
        "CUBR_SOURCE_COMMIT": source_commit,
        "CUBR_PROBE_SOURCE_SHA256": sha256_path(probe_source),
        "CUBR_PROBE_BINARY_SHA256": sha256_path(probe),
        "CUBR_RUNNER_SHA256": sha256_path(Path(__file__).resolve()),
        "CUBR_PREREG_SHA256": sha256_path(prereg),
        "CUBR_HOST": platform.node(),
        "CUBR_RUSTC": rustc,
    })
    command = [str(probe), str(corpus_root), str(output)]
    if shutil.which("taskset"):
        command = ["taskset", "--cpu-list", "0", *command]
    completed = subprocess.run(command, cwd=repo_root, env=env, text=True, capture_output=True)
    if completed.returncode != 0:
        raise MeasurementVoid(f"probe failed with {completed.returncode}: {completed.stderr.strip()}")
    try:
        bundle = json.loads(output.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise MeasurementVoid(f"probe did not produce JSON: {error}") from error
    manifest_path = corpus_root / "manifest.v3.json"
    manifest = json.loads(manifest_path.read_text())
    expected_provenance = {
        "source_commit": source_commit,
        "probe_source_sha256": sha256_path(probe_source),
        "probe_binary_sha256": sha256_path(probe),
        "runner_sha256": sha256_path(Path(__file__).resolve()),
        "prereg_sha256": sha256_path(prereg),
        "manifest_sha256": sha256_path(manifest_path),
        "host": platform.node(),
        "arch": platform.machine().lower(),
        "cpu_affinity": "0",
        "rustc": rustc,
    }
    provenance = bundle.get("provenance", {})
    for key, expected in expected_provenance.items():
        if provenance.get(key) != expected:
            raise MeasurementVoid(f"provenance mismatch for {key}: {provenance.get(key)!r} != {expected!r}")
    measurement = validate_bundle(bundle, manifest)
    after = admission_snapshot()
    assert_admitted(after, "after")
    bundle["admission"] = {"before": before, "after": after}
    bundle["measurement"] = measurement
    bundle["measurement"]["probe_stderr"] = completed.stderr.strip()
    write_json_atomically(output, bundle)
    print(json.dumps(measurement, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MeasurementVoid as error:
        raise SystemExit(f"VOID: {error}")
