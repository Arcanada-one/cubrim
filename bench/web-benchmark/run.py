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
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from adapters import (
    CodecAdapter,
    SubprocessExecutor,
    ToolIdentity,
    candidate_adapters,
    phase_a_adapters,
)
from capabilities import PHASE_A_CODECS, energy_capability, validate_codec_attribution
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


SAFE_JOURNAL_FIELDS = (
    "sample_id",
    "codec_key",
    "trial_no",
    "randomized_order",
    # Load is carried in milli-units because the journal admits ints and str
    # only; a float would be silently dropped and the record would say a run
    # was refused without saying how loaded the host was.
    "load_per_cpu_milli",
)
SAFE_REASON_RE = re.compile(r"^[a-z0-9_]+$")
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SAMPLE_FIELDS = {
    "sample_id",
    "path",
    "sha256",
    "byte_count",
    "media_type",
    "size_class",
    "media_family",
    "source_ref",
    "license_id",
    "redistributable",
}
# Corpus v2 carries the real-world provenance the generated v1 fixtures could
# not: an attribution per sample, and a record of the content types that are
# absent rather than faked. Field sets stay closed per schema version.
MANIFEST_V2_SAMPLE_FIELDS = MANIFEST_SAMPLE_FIELDS | {"attribution"}
MANIFEST_TOP_LEVEL = {
    1: {"schema_version", "samples"},
    2: {"schema_version", "corpus_key", "provenance", "gaps", "samples"},
}
MANIFEST_SAMPLE_FIELDS_BY_VERSION = {
    1: MANIFEST_SAMPLE_FIELDS,
    2: MANIFEST_V2_SAMPLE_FIELDS,
}


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
    # One sample every 25 trials: ~78 reads across a 1950-trial Phase A run,
    # frequent enough that a load ramp is caught within seconds of the
    # 1-minute average reflecting it.
    ADMISSION_RECHECK_EVERY = 25

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
        manifest_path: Path | None = None,
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
        self.manifest_path = manifest_path
        self._samples: tuple[BenchmarkSample, ...] = ()
        self._identities: dict[str, tuple[ToolIdentity, dict[str, object]]] = {}
        self._run_timing: dict[str, str] | None = None
        # The adapters a run actually executed. The bundle describes itself
        # from this rather than from PHASE_A_CODECS, so a candidate run
        # cannot be emitted wearing the published Phase A label.
        self._adapters: tuple[CodecAdapter, ...] = ()

    @classmethod
    def for_bundle_only(
        cls,
        *,
        runner_code_sha: str,
        environment: dict[str, object],
    ) -> "PhaseARunner":
        runner = cls(
            corpus_root=Path("."),
            output_root=Path("."),
            journal=RedactedJournal(Path("journal/unused.jsonl")),
            runner_code_sha=runner_code_sha,
            environment=environment,
            config=RunnerConfig(),
            executor=SubprocessExecutor(60),
        )
        runner._run_timing = {
            "started_at": "2000-01-01T00:00:00Z",
            "completed_at": "2000-01-01T00:00:01Z",
        }
        return runner

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
        cached = self._identities.get(adapter.name)
        identity = cached[0] if cached is not None else adapter.identity()
        if not getattr(identity, "codec_build_provenance_sha256", None):
            raise ValueError("measured trials require immutable codec build provenance")
        self.output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="trial-", dir=self.output_root) as directory:
            trial_dir = Path(directory)
            compressed = trial_dir / "compressed.bin"
            decoded = trial_dir / "decoded.bin"
            compression = self.executor.compress(adapter, identity, source, compressed)
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
            decompression = self.executor.decompress(adapter, identity, compressed, decoded)
            decoded_bytes = decoded.stat().st_size
            decoded_sha256 = hash_file(decoded, max_bytes=self.config.max_output_bytes)
            if decoded_sha256 != decompression.output_sha256:
                raise ValueError("decoded output hash disagrees with the executor")
        if decoded_sha256 != original_sha256 or decoded_bytes != original_bytes:
            raise RoundTripError("decoded output failed exact lossless round trip")
        identity_json = _identity_json(identity, adapter.capabilities)
        tool_fingerprint = stable_fingerprint(identity_json)
        environment_fingerprint = stable_fingerprint(self.environment)
        return TrialRecord(
            sample_id=sample.sample_id,
            codec_key=adapter.name,
            trial_no=trial_no,
            randomized_order=randomized_order,
            measured_at=utc_now(),
            runner_code_sha=self.runner_code_sha,
            codec_build_provenance_sha256=identity.codec_build_provenance_sha256,
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
                "compression_ratio": (
                    compressed_bytes / original_bytes if original_bytes else 0.0
                ),
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
        if self._run_timing is None:
            raise RuntimeError("bundle timing is unavailable before benchmark execution")
        samples = self._samples
        manifest_sha256 = (
            hash_file(self.manifest_path)
            if self.manifest_path is not None
            else stable_fingerprint([sample.as_json() for sample in samples])
        )
        manifest_schema_version = (
            json.loads(self.manifest_path.read_text(encoding="utf-8"))["schema_version"]
            if self.manifest_path is not None
            else 1
        )
        ran = tuple(a.name for a in self._adapters) or PHASE_A_CODECS
        # Phase A is the published five-codec comparison and nothing else. Any
        # other adapter set is a candidate run and must say so: a bundle that
        # claimed "A" while containing our own codec would be indistinguishable
        # from the real thing downstream.
        is_phase_a = ran == PHASE_A_CODECS
        incremental = any(
            bool(a.capabilities.get("incremental_decode")) for a in self._adapters
        )
        return {
            "schema_version": 1,
            "scope": "resource_codec",
            "phase": "A" if is_phase_a else "B",
            "run_timing": self._run_timing,
            "corpus": {
                "manifest_name": (
                    self.manifest_path.name
                    if self.manifest_path is not None
                    else "inline-fixture"
                ),
                "manifest_sha256": manifest_sha256,
                "manifest_schema_version": manifest_schema_version,
                "sample_count": len(samples),
                "samples": [sample.as_json() for sample in samples],
            },
            "toolchain": [
                _identity_json(identity, capabilities)
                for identity, capabilities in (
                    self._identities[name] for name in sorted(self._identities)
                )
            ],
            "protocol": {
                "codecs": list(ran),
                "warmups": self.config.warmups,
                "trials_per_cell": self.config.trials,
                "randomized_order_seed": self.config.random_seed,
                "bootstrap_iterations": 5_000,
                "bootstrap_confidence": 0.95,
                "timeout_seconds": self.config.timeout_seconds,
                "max_input_bytes": self.config.max_input_bytes,
                "max_output_bytes": self.config.max_output_bytes,
                "max_expansion_ratio": self.config.max_expansion_ratio,
                "network_isolation": "systemd_user_unit_plus_seccomp_network_deny",
                "wall_clock": "time.monotonic_ns",
                "peak_rss": "gnu_time_verbose",
            },
            "environment": self.environment,
            "applicability": {
                "time_to_first_decoded_byte": {
                    "available": incremental,
                    "reason": (
                        "an_incremental_decoder_is_present"
                        if incremental
                        else "phase_a_codecs_do_not_offer_incremental_decode"
                    ),
                },
                "energy": {
                    "available": False,
                    "reason": "readable_calibrated_rapl_unavailable",
                },
            },
            "resource_results": [trial.as_json() for trial in trials],
            "resource_summaries": [],
            "page_results": {
                "explicit_wasm_application": [],
                "transparent_http_page": [],
            },
        }


    def _reassert_admission(self, order: int) -> None:
        """Refuse to keep measuring on a host that stopped being quiet.

        Sampled rather than measured every trial: reading /proc/loadavg 1950
        times would itself be work, and the 1-minute average cannot move
        meaningfully between neighbouring trials anyway.
        """
        if order % self.ADMISSION_RECHECK_EVERY != 1:
            return
        load_per_cpu = _current_load_per_cpu()
        if load_per_cpu is None:
            return
        if (
            self.observed_max_load_per_cpu is None
            or load_per_cpu > self.observed_max_load_per_cpu
        ):
            self.observed_max_load_per_cpu = load_per_cpu
        if self._load_ceiling is not None and load_per_cpu > self._load_ceiling:
            self.journal.write(
                "failed_admission_midrun",
                {
                    "randomized_order": order,
                    "load_per_cpu_milli": int(round(load_per_cpu * 1000)),
                },
            )
            raise RuntimeError(
                "host admission lapsed during the run; timings after this point "
                "would not be comparable to the ones before it"
            )

    def execute(
        self,
        samples: tuple[BenchmarkSample, ...],
        adapters: tuple[CodecAdapter, ...],
    ) -> dict[str, object]:
        self._run_timing = {"started_at": utc_now(), "completed_at": ""}
        admission = self.environment.get("admission")
        if not isinstance(admission, dict) or admission.get("accepted") is not True:
            self.journal.write("failed_admission", {})
            raise RuntimeError("host admission rejected the benchmark run")
        ceiling = admission.get("max_load_per_cpu")
        self._load_ceiling = ceiling if isinstance(ceiling, (int, float)) else None
        start_load = admission.get("load_per_cpu")
        self.observed_max_load_per_cpu = (
            start_load if isinstance(start_load, (int, float)) else None
        )
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._samples = samples
        self._adapters = tuple(adapters)
        self._identities = {}
        for adapter in adapters:
            try:
                # The attribution gate existed, was tested, and was invoked by
                # nothing: a Cubrim-Web row could have been produced by an
                # adapter with no Web Profile capability and the gate would
                # never have run. It guards the run from here.
                validate_codec_attribution(adapter.name, adapter.capabilities)
                self._identities[adapter.name] = (
                    adapter.identity(),
                    dict(adapter.capabilities),
                )
            except (FileNotFoundError, RuntimeError, ValueError):
                self.journal.write(
                    "tool_provenance_mismatch",
                    {"codec_key": adapter.name},
                )
                raise
        for sample in samples:
            for adapter in adapters:
                for warmup_no in range(1, self.config.warmups + 1):
                    warmup = self.try_trial(
                        sample,
                        adapter,
                        trial_no=-warmup_no,
                        randomized_order=warmup_no,
                    )
                    if warmup is None:
                        raise RuntimeError(
                            f"warmup failed: {sample.sample_id}/{adapter.name}"
                        )
        schedule = [
            (sample, adapter, trial_no)
            for trial_no in range(1, self.config.trials + 1)
            for sample in samples
            for adapter in adapters
        ]
        random.Random(self.config.random_seed).shuffle(schedule)
        results = []
        for order, (sample, adapter, trial_no) in enumerate(schedule, start=1):
            # Admission is a property of the whole measurement window, not of
            # its first instant. Checking it once and trusting it for the rest
            # of the run lets a host that was quiet at the start contaminate
            # every timing taken after it stopped being quiet, and the bundle
            # would still carry `accepted: true` beside the load figure from
            # before the ramp.
            self._reassert_admission(order)
            trial = self.try_trial(
                sample,
                adapter,
                trial_no=trial_no,
                randomized_order=order,
            )
            if trial is not None:
                results.append(trial)
        _require_complete_cells(results, samples, adapters, self.config.trials)
        self._run_timing["completed_at"] = utc_now()
        from summarize import finalize_bundle

        return finalize_bundle(
            self.bundle(results),
            seed=self.config.random_seed,
        )


def load_samples(manifest_path: Path) -> tuple[BenchmarkSample, ...]:
    if manifest_path.stat().st_size > 1024 * 1024:
        raise ValueError("web corpus manifest exceeds the configured maximum")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = data.get("schema_version") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or version not in MANIFEST_TOP_LEVEL
        or set(data) != MANIFEST_TOP_LEVEL[version]
        or not isinstance(data.get("samples"), list)
        or not data["samples"]
    ):
        raise ValueError("unsupported web corpus manifest")
    sample_fields = MANIFEST_SAMPLE_FIELDS_BY_VERSION[version]
    for row in data["samples"]:
        if not isinstance(row, dict) or set(row) != sample_fields:
            raise ValueError("web corpus sample fields are not closed")
    samples = tuple(
        BenchmarkSample(
            sample_id=row["sample_id"],
            path=row["path"],
            sha256=row["sha256"],
            byte_count=row["byte_count"],
            media_type=row["media_type"],
            size_class=row["size_class"],
            media_family=row["media_family"],
            source_ref=row["source_ref"],
            license_id=row["license_id"],
            redistributable=row["redistributable"],
            attribution=row.get("attribution"),
        )
        for row in data["samples"]
    )
    ids = [sample.sample_id for sample in samples]
    paths = [sample.path for sample in samples]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError("manifest contains duplicate sample IDs or paths")
    return samples


def _current_load_per_cpu() -> float | None:
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    load_1m = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    if load_1m is None or not affinity:
        return None
    return load_1m / len(affinity)


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
    SubprocessExecutor.verify_network_sandbox()
    identities = []
    for adapter in phase_a_adapters():
        try:
            identity = adapter.identity()
            identities.append(_identity_json(identity, adapter.capabilities))
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
        "network_isolation": "systemd_user_unit_plus_seccomp_network_deny",
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
        cwd=REPO_ROOT,
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
            cwd=REPO_ROOT,
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00",
        "Z",
    )


def _identity_json(
    identity: ToolIdentity | object,
    capabilities: dict[str, bool],
) -> dict[str, object]:
    if hasattr(identity, "as_json"):
        return identity.as_json(capabilities)
    return {
        "name": identity.name,
        "version": identity.version,
        "binary_path": identity.binary_path,
        "binary_sha256": identity.binary_sha256,
        "flags": list(identity.flags),
        "capabilities": dict(sorted(capabilities.items())),
        "binary_package": identity.binary_package,
        "binary_package_version": identity.binary_package_version,
        "source_package": identity.source_package,
        "source_package_version": identity.source_package_version,
        "upstream_release_sha": identity.upstream_release_sha,
        "upstream_source_reference": identity.upstream_source_reference,
        "codec_build_provenance_sha256": identity.codec_build_provenance_sha256,
    }


def atomic_write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-a", action="store_true", required=True)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "web-corpus" / "manifest.v3.json",
    )
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    parser.add_argument("--journal", type=Path, default=Path(__file__).parent / "journal")
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument(
        "--candidate",
        action="store_true",
        help=(
            "measure the candidate channel alongside the five incumbents in one "
            "randomized schedule, and write candidate.json. The published "
            "phase-a.json is never written by this path."
        ),
    )
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
        manifest_path=args.manifest,
    )
    # A candidate is compared within a single run, not against numbers measured
    # on another day: the incumbents are re-measured in the same randomized
    # schedule so both sides see the same host. Those incumbent numbers land in
    # candidate.json and never overwrite the published Phase A bundle.
    adapters_to_run = (
        phase_a_adapters() + candidate_adapters()
        if args.candidate
        else phase_a_adapters()
    )
    bundle = runner.execute(samples, adapters_to_run)
    args.out.mkdir(parents=True, exist_ok=True)
    output_path = args.out / ("candidate.json" if args.candidate else "phase-a.json")
    atomic_write_json(output_path, bundle)
    observed = runner.observed_max_load_per_cpu
    print(
        json.dumps(
            {
                "bundle": str(output_path),
                "trials": len(bundle["resource_results"]),
                # Reported beside the run, not folded into the bundle: the
                # bundle records the host as admitted, and the reader deserves
                # to know how far the host moved while it was being measured.
                "max_load_per_cpu_observed": (
                    round(observed, 3) if observed is not None else None
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
