#!/usr/bin/env python3
"""Capability-gated Phase A resource benchmark runner."""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Mapping

from adapters import CodecAdapter, SubprocessExecutor, phase_a_adapters
from capabilities import PHASE_A_CODECS, energy_capability
from model import (
    CODE_SHA_RE,
    BenchmarkSample,
    RoundTripError,
    RunnerConfig,
    TrialRecord,
    enforce_size_limits,
    hash_file,
    resolve_contained,
    stable_fingerprint,
)


SAFE_JOURNAL_FIELDS = ("sample_id", "codec_key", "trial_no", "randomized_order")
SAFE_REASON_RE = re.compile(r"^[a-z0-9_]+$")


class RedactedJournal:
    def __init__(self, path: Path):
        self.path = path

    def write(self, reason: str, context: Mapping[str, object]) -> None:
        safe_reason = reason if SAFE_REASON_RE.fullmatch(reason) else "failure"
        record = {"reason": safe_reason}
        for key in SAFE_JOURNAL_FIELDS:
            value = context.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                record[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


class PhaseARunner:
    def __init__(
        self,
        *,
        corpus_root: Path,
        output_root: Path,
        journal: RedactedJournal,
        runner_code_sha: str,
        environment: dict[str, object],
        config: RunnerConfig,
        executor: SubprocessExecutor,
    ):
        if not CODE_SHA_RE.fullmatch(runner_code_sha):
            raise ValueError("runner code SHA must be 40 or 64 lowercase hex characters")
        self.corpus_root = corpus_root
        self.output_root = output_root
        self.journal = journal
        self.runner_code_sha = runner_code_sha
        self.environment = {**environment, "code_sha": runner_code_sha}
        self.config = config
        self.executor = executor

    @classmethod
    def for_bundle_only(
        cls,
        *,
        runner_code_sha: str,
        environment: dict[str, object],
    ) -> "PhaseARunner":
        return cls(
            corpus_root=Path("."),
            output_root=Path("."),
            journal=RedactedJournal(Path("journal/unused.jsonl")),
            runner_code_sha=runner_code_sha,
            environment=environment,
            config=RunnerConfig(),
            executor=SubprocessExecutor(60),
        )

    def run_trial(
        self,
        sample: BenchmarkSample,
        adapter: CodecAdapter,
        *,
        trial_no: int,
        randomized_order: int,
    ) -> TrialRecord:
        source = resolve_contained(self.corpus_root, sample.path)
        original_bytes = source.stat().st_size
        original_sha256 = hash_file(source, max_bytes=self.config.max_input_bytes)
        if original_bytes != sample.byte_count or original_sha256 != sample.sha256:
            raise ValueError("payload does not match its immutable manifest")
        identity = adapter.identity()
        if identity.codec_code_sha is None:
            raise ValueError("measured trials require an explicit codec code SHA")
        self.output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="trial-", dir=self.output_root) as directory:
            trial_dir = Path(directory)
            compressed = trial_dir / "compressed.bin"
            decoded = trial_dir / "decoded.bin"
            compression = self.executor.compress(adapter, source, compressed)
            compressed_bytes = compressed.stat().st_size
            compressed_sha256 = hash_file(compressed)
            if compressed_sha256 != compression.output_sha256:
                raise ValueError("compressed output hash disagrees with the executor")
            enforce_size_limits(
                original_bytes,
                compressed_bytes,
                max_input_bytes=self.config.max_input_bytes,
                max_output_bytes=self.config.max_output_bytes,
                max_expansion_ratio=self.config.max_expansion_ratio,
            )
            decompression = self.executor.decompress(adapter, compressed, decoded)
            decoded_bytes = decoded.stat().st_size
            decoded_sha256 = hash_file(decoded, max_bytes=self.config.max_output_bytes)
            if decoded_sha256 != decompression.output_sha256:
                raise ValueError("decoded output hash disagrees with the executor")
        if decoded_sha256 != original_sha256 or decoded_bytes != original_bytes:
            raise RoundTripError("decoded output failed exact lossless round trip")
        tool_fingerprint = stable_fingerprint(identity.__dict__)
        environment_fingerprint = stable_fingerprint(self.environment)
        return TrialRecord(
            sample_id=sample.sample_id,
            codec_key=adapter.name,
            trial_no=trial_no,
            randomized_order=randomized_order,
            runner_code_sha=self.runner_code_sha,
            codec_code_sha=identity.codec_code_sha,
            environment_fingerprint=environment_fingerprint,
            tool_fingerprint=tool_fingerprint,
            tool_version=identity.version,
            tool_binary_sha256=identity.binary_sha256,
            tool_flags=identity.flags,
            original_sha256=original_sha256,
            compressed_sha256=compressed_sha256,
            decoded_sha256=decoded_sha256,
            original_bytes=original_bytes,
            compressed_bytes=compressed_bytes,
            decoded_bytes=decoded_bytes,
            roundtrip_exact=True,
            metrics={
                "compressed_bytes": compressed_bytes,
                "compression_duration": compression.duration_ns / 1_000_000,
                "decompression_duration": decompression.duration_ns / 1_000_000,
                "peak_memory": max(compression.peak_rss_bytes, decompression.peak_rss_bytes),
            },
        )

    def try_trial(
        self,
        sample: BenchmarkSample,
        adapter: CodecAdapter,
        *,
        trial_no: int,
        randomized_order: int,
    ) -> TrialRecord | None:
        context = {
            "sample_id": sample.sample_id,
            "codec_key": adapter.name,
            "trial_no": trial_no,
            "randomized_order": randomized_order,
        }
        try:
            return self.run_trial(
                sample,
                adapter,
                trial_no=trial_no,
                randomized_order=randomized_order,
            )
        except (TimeoutError, subprocess.TimeoutExpired):
            self.journal.write("timeout", context)
        except RoundTripError:
            self.journal.write("corrupt_output", context)
        except PermissionError:
            self.journal.write("inaccessible_instrumentation", context)
        except (FileNotFoundError, ValueError):
            self.journal.write("invalid_input_or_capability", context)
        except (OSError, RuntimeError):
            self.journal.write("crash", context)
        return None

    def bundle(self, trials: Iterable[TrialRecord]) -> dict[str, object]:
        return {
            "schema_version": 1,
            "scope": "resource_codec",
            "environment": self.environment,
            "resource_results": [trial.as_json() for trial in trials],
            "page_results": {
                "explicit_wasm_application": [],
                "transparent_http_page": [],
            },
        }

    def execute(
        self,
        samples: tuple[BenchmarkSample, ...],
        adapters: tuple[CodecAdapter, ...],
    ) -> dict[str, object]:
        admission = self.environment.get("admission")
        if isinstance(admission, dict) and admission.get("accepted") is not True:
            self.journal.write("failed_admission", {})
            raise RuntimeError("host admission rejected the benchmark run")
        self.output_root.mkdir(parents=True, exist_ok=True)
        for sample in samples:
            for adapter in adapters:
                for warmup_no in range(1, self.config.warmups + 1):
                    self.try_trial(
                        sample,
                        adapter,
                        trial_no=-warmup_no,
                        randomized_order=warmup_no,
                    )
        schedule = [
            (sample, adapter, trial_no)
            for trial_no in range(1, self.config.trials + 1)
            for sample in samples
            for adapter in adapters
        ]
        random.Random(self.config.random_seed).shuffle(schedule)
        results = [
            trial
            for order, (sample, adapter, trial_no) in enumerate(schedule, start=1)
            if (
                trial := self.try_trial(
                    sample,
                    adapter,
                    trial_no=trial_no,
                    randomized_order=order,
                )
            )
            is not None
        ]
        _require_complete_cells(results, samples, adapters, self.config.trials)
        return self.bundle(results)


def load_samples(manifest_path: Path) -> tuple[BenchmarkSample, ...]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("samples"), list):
        raise ValueError("unsupported web corpus manifest")
    samples = tuple(
        BenchmarkSample(
            sample_id=row["sample_id"],
            path=row["path"],
            sha256=row["sha256"],
            byte_count=row["byte_count"],
            media_type=row["media_type"],
            size_class=row["size_class"],
        )
        for row in data["samples"]
    )
    ids = [sample.sample_id for sample in samples]
    paths = [sample.path for sample in samples]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError("manifest contains duplicate sample IDs or paths")
    return samples


def capture_environment(code_sha: str) -> dict[str, object]:
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    load_1m = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    load_per_cpu = load_1m / len(affinity) if load_1m is not None and affinity else None
    temperatures = _temperatures()
    max_temperature = max(temperatures) if temperatures else None
    cpu = platform.processor() or _cpu_model()
    accepted_load = load_per_cpu is None or load_per_cpu <= 1.0
    accepted_temperature = max_temperature is None or max_temperature < 90
    admission = {
        "load_1m": load_1m,
        "load_per_cpu": load_per_cpu,
        "max_load_per_cpu": 1.0,
        "temperature_c": max_temperature,
        "max_temperature_c": 90,
        "accepted": accepted_load and accepted_temperature,
    }
    return {
        "code_sha": code_sha,
        "host": platform.node(),
        "cpu": cpu,
        "os": platform.platform(),
        "affinity": affinity,
        "admission": admission,
    }


def preflight(
    manifest_path: Path,
    journal: RedactedJournal,
) -> dict[str, object]:
    samples = load_samples(manifest_path)
    for sample in samples:
        source = resolve_contained(manifest_path.parent, sample.path)
        if source.stat().st_size != sample.byte_count or hash_file(source) != sample.sha256:
            raise ValueError(f"manifest mismatch for {sample.sample_id}")
    if not Path("/usr/bin/time").is_file():
        raise FileNotFoundError("/usr/bin/time is required")
    identities = []
    for adapter in phase_a_adapters():
        try:
            identities.append(adapter.identity().__dict__)
        except (FileNotFoundError, RuntimeError, ValueError):
            journal.write("tool_provenance_mismatch", {"codec_key": adapter.name})
            raise
    code_sha = _git_code_sha()
    environment = capture_environment(code_sha)
    counter = next(iter(sorted(Path("/sys/class/powercap").glob("intel-rapl*/energy_uj"))), None)
    energy = energy_capability(counter, None) if counter is not None else None
    if energy is None:
        journal.write("energy_unavailable", {"codec_key": "host"})
    return {
        "phase": "A",
        "codecs": list(PHASE_A_CODECS),
        "sample_count": len(samples),
        "gnu_time": "/usr/bin/time",
        "tools": identities,
        "environment": environment,
        "energy": energy if energy is not None else {"available": False},
        "page_results": {
            "explicit_wasm_application": [],
            "transparent_http_page": [],
        },
    }


def _require_complete_cells(
    results: list[TrialRecord],
    samples: tuple[BenchmarkSample, ...],
    adapters: tuple[CodecAdapter, ...],
    required_trials: int,
) -> None:
    counts: dict[tuple[str, str], set[int]] = {}
    for trial in results:
        counts.setdefault((trial.sample_id, trial.codec_key), set()).add(trial.trial_no)
    for sample in samples:
        for adapter in adapters:
            if len(counts.get((sample.sample_id, adapter.name), set())) != required_trials:
                raise RuntimeError(
                    f"incomplete valid trial cell: {sample.sample_id}/{adapter.name}"
                )


def _git_code_sha(*, require_clean: bool = False) -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
        timeout=5,
    )
    code_sha = completed.stdout.strip()
    if not CODE_SHA_RE.fullmatch(code_sha):
        raise ValueError("git HEAD is not a supported code SHA")
    if require_clean:
        status = subprocess.run(
            ("git", "status", "--porcelain", "--untracked-files=normal"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            timeout=5,
        )
        if status.stdout.strip():
            raise RuntimeError("measured runs require a clean committed runner tree")
    return code_sha


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    except OSError:
        pass
    return "unknown"


def _temperatures() -> list[float]:
    values = []
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            raw = float(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            continue
        values.append(raw / 1000 if raw > 1000 else raw)
    return values


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-a", action="store_true", required=True)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "web-corpus" / "manifest.v1.json",
    )
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    parser.add_argument("--journal", type=Path, default=Path(__file__).parent / "journal")
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    journal = RedactedJournal(args.journal / "voids.jsonl")
    config = RunnerConfig(trials=args.trials, warmups=args.warmups)
    if args.preflight:
        print(json.dumps(preflight(args.manifest, journal), indent=2, sort_keys=True))
        return 0
    samples = load_samples(args.manifest)
    code_sha = _git_code_sha(require_clean=True)
    runner = PhaseARunner(
        corpus_root=args.manifest.parent,
        output_root=args.out,
        journal=journal,
        runner_code_sha=code_sha,
        environment=capture_environment(code_sha),
        config=config,
        executor=SubprocessExecutor(config.timeout_seconds, config.max_output_bytes),
    )
    bundle = runner.execute(samples, phase_a_adapters())
    args.out.mkdir(parents=True, exist_ok=True)
    output_path = args.out / "phase-a-results.json"
    output_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"bundle": str(output_path), "trials": len(bundle["resource_results"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
