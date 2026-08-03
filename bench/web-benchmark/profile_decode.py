#!/usr/bin/env python3
"""Release-mode, stage-attribution runner for CUBR-0075's first slice."""

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "bench" / "web-corpus" / "manifest.v2.json"
SIZE_BOUNDARY = 64 * 1024
STAGE_NAMES = (
    "framing",
    "entropy",
    "transforms",
    "match_copy",
    "allocation",
    "output_materialization",
)
AFFINITY_MODES = ("one-core", "fixed-core")
DEFAULT_TRIALS = 30
DEFAULT_WARMUPS = 3


class ProfileBlocked(RuntimeError):
    """A measurement cannot be represented as complete evidence."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def size_band(byte_count: int) -> str:
    return "above-64KiB" if byte_count > SIZE_BOUNDARY else "at-or-below-64KiB"


def contained_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ProfileBlocked(f"manifest path escapes corpus root: {relative}") from exc
    return candidate


def load_manifest(path: Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2:
        raise ProfileBlocked("CUBR-0075 requires manifest schema_version=2")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or len(samples) != 12:
        raise ProfileBlocked("CUBR-0075 requires exactly 12 v2 samples")
    root = path.parent
    checked: list[dict[str, Any]] = []
    for sample in samples:
        required = {"sample_id", "path", "sha256", "byte_count"}
        if not required.issubset(sample):
            raise ProfileBlocked("v2 sample is missing an immutable identity field")
        source = contained_path(root, str(sample["path"]))
        if not source.is_file():
            raise ProfileBlocked(f"manifest payload is absent: {sample['path']}")
        actual_bytes = source.stat().st_size
        actual_sha = sha256_file(source)
        if actual_bytes != sample["byte_count"] or actual_sha != sample["sha256"]:
            raise ProfileBlocked(f"manifest payload changed: {sample['sample_id']}")
        checked_sample = dict(sample)
        checked_sample["_source"] = source
        checked_sample["size_band"] = size_band(actual_bytes)
        checked.append(checked_sample)
    return manifest, tuple(checked)


def affinity_argv(mode: str) -> tuple[str, ...]:
    if mode == "one-core":
        return ()
    if mode == "fixed-core":
        taskset = shutil.which("taskset")
        if taskset is None:
            raise ProfileBlocked("fixed-core measurement requires taskset")
        return (taskset, "--cpu-list", "0")
    raise ValueError(f"unknown affinity mode: {mode}")


def profile_argv(
    profile_binary: Path,
    archive: Path,
    original: Path,
    report: Path,
    mode: str,
) -> tuple[str, ...]:
    return affinity_argv(mode) + (
        str(profile_binary),
        "--input",
        str(archive),
        "--original",
        str(original),
        "--output",
        str(report),
        "--affinity",
        mode,
    )


def validate_profile_record(
    record: dict[str, Any], *, sample_id: str, original_sha256: str, original_bytes: int
) -> None:
    if record.get("exact_roundtrip") is not True:
        raise ProfileBlocked(f"profile round-trip failed: {sample_id}")
    if record.get("original_sha256") != original_sha256:
        raise ProfileBlocked(f"profile original hash drifted: {sample_id}")
    if record.get("original_bytes") != original_bytes:
        raise ProfileBlocked(f"profile original size drifted: {sample_id}")
    profile = record.get("decode_profile")
    if not isinstance(profile, dict):
        raise ProfileBlocked(f"profile record has no decode_profile: {sample_id}")
    rows = profile.get("stages")
    names = tuple(row.get("name") for row in rows) if isinstance(rows, list) else ()
    if names != STAGE_NAMES:
        raise ProfileBlocked(f"profile stage contract mismatch: {sample_id}")
    if profile.get("output_bytes") != original_bytes:
        raise ProfileBlocked(f"profile output size drifted: {sample_id}")


def _median(values: Iterable[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return statistics.median(present) if present else None


def summarize_observations(observations: list[dict[str, Any]]) -> dict[str, Any]:
    if not observations:
        raise ProfileBlocked("cannot summarize an empty observation set")
    profile_rows = [observation["decode_profile"] for observation in observations]
    stages: dict[str, dict[str, Any]] = {}
    for index, name in enumerate(STAGE_NAMES):
        rows = [profile["stages"][index] for profile in profile_rows]
        stages[name] = {
            "applicable": all(row["applicable"] for row in rows),
            "calls_median": _median(row["calls"] for row in rows),
            "nanos_per_output_byte_median": _median(
                row["nanos_per_output_byte"] for row in rows
            ),
            "cycles_per_output_byte_median": _median(
                row["cycles_per_output_byte"] for row in rows
            ),
        }
    return {
        "trials": len(observations),
        "exact_roundtrip_all": all(
            observation["exact_roundtrip"] for observation in observations
        ),
        "total_nanos_median": _median(
            observation["decode_profile"]["total_nanos"] for observation in observations
        ),
        "total_cycles_median": _median(
            observation["decode_profile"]["total_cycles"] for observation in observations
        ),
        "stages": stages,
    }


def _git_sha() -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _run_profile_once(
    *,
    profile_binary: Path,
    archive: Path,
    original: Path,
    sample: dict[str, Any],
    mode: str,
    trial_no: int,
    warmup: bool,
    output_dir: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    report_path = output_dir / f"{sample['sample_id']}-{mode}-{trial_no}.json"
    command = profile_argv(profile_binary, archive, original, report_path, mode)
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ProfileBlocked(
            f"profile command failed for {sample['sample_id']} {mode} trial {trial_no}: {detail[-500:]}"
        ) from exc
    record = json.loads(report_path.read_text(encoding="utf-8"))
    validate_profile_record(
        record,
        sample_id=str(sample["sample_id"]),
        original_sha256=str(sample["sha256"]),
        original_bytes=int(sample["byte_count"]),
    )
    return {
        "trial_no": trial_no,
        "warmup": warmup,
        "affinity_mode": mode,
        "exact_roundtrip": record["exact_roundtrip"],
        "mode": record["mode"],
        "decode_profile": record["decode_profile"],
        "allocation": record["allocation"],
        "original_sha256": record["original_sha256"],
        "decoded_sha256": record["decoded_sha256"],
    }


def run_profile(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    profile_binary: Path,
    encoder_binary: Path,
    output_path: Path,
    trials: int = DEFAULT_TRIALS,
    warmups: int = DEFAULT_WARMUPS,
    timeout_seconds: float = 900.0,
) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials must be positive")
    if warmups < 0:
        raise ValueError("warmups cannot be negative")
    manifest, samples = load_manifest(manifest_path)
    source_sha = _git_sha()
    profile_binary = profile_binary.resolve()
    encoder_binary = encoder_binary.resolve()
    if not profile_binary.is_file() or not encoder_binary.is_file():
        raise ProfileBlocked("release profiler and encoder binaries must both exist")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_sha = sha256_file(manifest_path)
    evidence: dict[str, Any] = {
        "kind": "cubr0075-decode-attribution",
        "schema_version": 1,
        "status": "complete",
        "task_id": "CUBR-0075",
        "source_sha": source_sha,
        "manifest_path": str(manifest_path.relative_to(REPO_ROOT)),
        "manifest_sha256": manifest_sha,
        "profile_binary": str(profile_binary),
        "profile_binary_sha256": sha256_file(profile_binary),
        "encoder_binary": str(encoder_binary),
        "encoder_binary_sha256": sha256_file(encoder_binary),
        "host": {
            "hostname": platform.node(),
            "system": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "protocol": {
            "warmups": warmups,
            "trials": trials,
            "affinity_modes": list(AFFINITY_MODES),
            "one_core_definition": "single decoder thread without an affinity mask",
            "fixed_core_definition": "single decoder thread under taskset --cpu-list 0",
            "execution_model": "single-threaded decoder; browser main-thread relevance only",
            "release_mode": True,
        },
        "samples": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    corpus_root = manifest_path.parent
    with tempfile.TemporaryDirectory(prefix="cubr0075-profile-") as temporary:
        temporary_root = Path(temporary)
        for sample in samples:
            source = sample["_source"]
            archive = temporary_root / f"{sample['sample_id']}.cub"
            subprocess.run(
                (
                    str(encoder_binary),
                    "compress",
                    str(source),
                    str(archive),
                    "--preset",
                    "lowmem-decode",
                    "--b",
                    "1024",
                    "-q",
                ),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
            )
            archive_sha = sha256_file(archive)
            sample_evidence: dict[str, Any] = {
                "sample_id": sample["sample_id"],
                "media_family": sample["media_family"],
                "size_class": sample["size_class"],
                "original_bytes": sample["byte_count"],
                "archive_bytes": archive.stat().st_size,
                "archive_sha256": archive_sha,
                "size_band": sample["size_band"],
                "observations": [],
                "summary": {},
            }
            with tempfile.TemporaryDirectory(
                prefix=f"{sample['sample_id']}-reports-", dir=temporary_root
            ) as report_directory:
                report_root = Path(report_directory)
                for mode in AFFINITY_MODES:
                    mode_observations: list[dict[str, Any]] = []
                    for trial_no in range(1, warmups + trials + 1):
                        observation = _run_profile_once(
                            profile_binary=profile_binary,
                            archive=archive,
                            original=source,
                            sample=sample,
                            mode=mode,
                            trial_no=trial_no,
                            warmup=trial_no <= warmups,
                            output_dir=report_root,
                            timeout_seconds=timeout_seconds,
                        )
                        sample_evidence["observations"].append(observation)
                        if not observation["warmup"]:
                            mode_observations.append(observation)
                    sample_evidence["summary"][mode] = summarize_observations(
                        mode_observations
                    )
            evidence["samples"].append(sample_evidence)

    if len(evidence["samples"]) != 12:
        raise ProfileBlocked("profile did not produce all 12 sample rows")
    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--profile-binary", type=Path, required=True)
    parser.add_argument("--encoder-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    args = parser.parse_args()
    try:
        run_profile(
            manifest_path=args.manifest.resolve(),
            profile_binary=args.profile_binary,
            encoder_binary=args.encoder_binary,
            output_path=args.output,
            trials=args.trials,
            warmups=args.warmups,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, ProfileBlocked, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
