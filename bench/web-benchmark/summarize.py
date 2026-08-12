#!/usr/bin/env python3
"""Verify and atomically finalize a canonical Phase A benchmark bundle."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable

from capabilities import (
    CANDIDATE_CODECS,
    PHASE_A_CODECS,
    validate_codec_attribution,
)
from model import (
    CODE_SHA_RE,
    SHA256_RE,
    hash_file,
    require_finite_nonnegative,
    stable_fingerprint,
)


PHASE_A_METRICS = (
    "compressed_bytes",
    "compression_ratio",
    "compression_duration",
    "decompression_duration",
    "peak_memory",
)
CANONICAL_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "web-corpus" / "manifest.v3.json"
)
CANONICAL_MANIFEST_SHA256 = (
    "43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5"
)
CANONICAL_SAMPLE_IDENTITIES = (
    ("css-medium-tailwind-v2", "payloads-v2/tailwind.css"),
    ("html-large-web-codec-v2", "payloads-v2/html-large-web-codec-v2.html"),
    ("html-medium-home-v2", "payloads-v2/html-medium-home-v2.html"),
    ("javascript-medium-magic-string-v2", "payloads-v2/magic-string.umd.js"),
    ("javascript-medium-sourcemap-codec-v2", "payloads-v2/sourcemap-codec.umd.js"),
    ("javascript-small-resolve-uri-v2", "payloads-v2/resolve-uri.umd.js"),
    ("json-api-large-world-benchmark-v2", "payloads-v2/json-api-large-world-benchmark-v2.json"),
    ("json-api-medium-web-benchmark-v2", "payloads-v2/json-api-medium-web-benchmark-v2.json"),
    ("json-api-small-hypotheses-v2", "payloads-v2/json-api-small-hypotheses-v2.json"),
    ("source-map-large-magic-string-v2", "payloads-v2/magic-string.umd.js.map"),
    ("source-map-small-sourcemap-codec-v2", "payloads-v2/sourcemap-codec.umd.js.map"),
    ("wasm-medium-cubrim-decoder-v3", "payloads-v3/cubrim-web-decoder.wasm"),
    ("woff2-medium-inter-latin-v20", "payloads-v2/inter-latin.medium.woff2"),
)
RESOURCE_METRIC_UNITS = {
    "compressed_bytes": "bytes",
    "compression_ratio": "ratio",
    "compression_duration": "milliseconds",
    "decompression_duration": "milliseconds",
    "peak_memory": "bytes",
}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "scope",
    "phase",
    "run_timing",
    "corpus",
    "toolchain",
    "protocol",
    "environment",
    "applicability",
    "resource_results",
    "resource_summaries",
    "page_results",
}
RUN_TIMING_FIELDS = {"started_at", "completed_at"}
ENVIRONMENT_FIELDS = {"code_sha", "cpu", "os", "affinity", "admission"}
ADMISSION_FIELDS = {
    "load_1m",
    "load_per_cpu",
    "max_load_per_cpu",
    "temperature_c",
    "max_temperature_c",
    "accepted",
}
CORPUS_FIELDS = {
    "manifest_name",
    "manifest_sha256",
    "manifest_schema_version",
    "sample_count",
    "samples",
}
SAMPLE_FIELDS = {
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
# Corpus v2 records who a real resource belongs to. Field sets stay closed per
# schema version so a stray key still fails rather than passing unnoticed.
SAMPLE_FIELDS_BY_SCHEMA = {
    1: SAMPLE_FIELDS,
    2: SAMPLE_FIELDS | {"attribution"},
}
TOOL_FIELDS = {
    "name",
    "version",
    "binary_path",
    "binary_sha256",
    "flags",
    "capabilities",
    "binary_package",
    "binary_package_version",
    "source_package",
    "source_package_version",
    "upstream_release_sha",
    "upstream_source_reference",
    "codec_build_provenance_sha256",
}
PROTOCOL_FIELDS = {
    "codecs",
    "warmups",
    "trials_per_cell",
    "randomized_order_seed",
    "bootstrap_iterations",
    "bootstrap_confidence",
    "timeout_seconds",
    "max_input_bytes",
    "max_output_bytes",
    "max_expansion_ratio",
    "network_isolation",
    "wall_clock",
    "peak_rss",
}
TRIAL_FIELDS = {
    "sample_id",
    "codec_key",
    "trial_no",
    "randomized_order",
    "measured_at",
    "runner_code_sha",
    "codec_build_provenance_sha256",
    "environment_fingerprint",
    "tool_fingerprint",
    "tool_version",
    "tool_binary_sha256",
    "tool_flags",
    "original_sha256",
    "compressed_sha256",
    "decoded_sha256",
    "original_bytes",
    "compressed_bytes",
    "decoded_bytes",
    "roundtrip_exact",
    "metrics",
}
SUMMARY_FIELDS = {
    "sample_id",
    "codec_key",
    "metric_name",
    "unit",
    "median",
    "p95",
    "bootstrap_95",
    "sample_count",
    "trial_numbers",
    "values_sha256",
}


def expected_codecs(phase: str) -> tuple[str, ...]:
    """The codec set a bundle of this phase must contain, exactly.

    Phase A is the published five-codec comparison and its expected set is
    unchanged. Phase B is that same comparison plus the candidate, measured in
    one schedule so both sides saw the same host — which is why the incumbents
    are expected here too, and why a Phase B bundle missing one of them is as
    invalid as a Phase A bundle missing one.
    """
    if phase == "A":
        return PHASE_A_CODECS
    if phase == "B":
        return PHASE_A_CODECS + CANDIDATE_CODECS
    raise ValueError(f"unknown benchmark phase: {phase!r}")


def verify_bundle(
    bundle: dict[str, object],
    *,
    require_summaries: bool = True,
    require_canonical_corpus: bool = False,
) -> None:
    _require_exact_fields(bundle, TOP_LEVEL_FIELDS, "bundle")
    if bundle["schema_version"] != 1 or bundle["scope"] != "resource_codec":
        raise ValueError("bundle must use resource_codec schema version 1")
    if "voids" in bundle:
        raise ValueError("a bundle carrying void records is not a result")
    codecs = expected_codecs(bundle["phase"])
    run_timing = _verify_run_timing(bundle["run_timing"])
    _verify_environment(bundle["environment"])
    samples = _verify_corpus(bundle["corpus"])
    if require_canonical_corpus:
        _verify_canonical_corpus(bundle["corpus"])
    tools = _verify_toolchain(bundle["toolchain"], codecs)
    protocol = _verify_protocol(bundle["protocol"], codecs)
    _verify_applicability(bundle["applicability"], tools)
    if bundle["page_results"] != {
        "explicit_wasm_application": [],
        "transparent_http_page": [],
    }:
        raise ValueError("Phase A page scopes must remain distinct and empty")
    trials = bundle["resource_results"]
    if not isinstance(trials, list) or not trials:
        raise ValueError("bundle requires resource results")
    _verify_trials(
        trials,
        samples,
        tools,
        protocol,
        bundle["environment"],
        run_timing,
    )
    summaries = bundle["resource_summaries"]
    if not isinstance(summaries, list):
        raise ValueError("resource summaries must be an array")
    if require_summaries:
        expected = _summary_rows(
            trials,
            seed=protocol["randomized_order_seed"],
            bootstrap_iterations=protocol["bootstrap_iterations"],
        )
        if summaries != expected:
            raise ValueError("resource summary does not exactly match all valid trials")
    elif summaries:
        raise ValueError("unfinalized bundle must not carry partial summaries")


def _verify_environment(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("environment must be an object")
    if not CODE_SHA_RE.fullmatch(str(value.get("code_sha", ""))):
        raise ValueError("environment code_sha is required")
    _require_exact_fields(value, ENVIRONMENT_FIELDS, "environment")
    if not isinstance(value["cpu"], str) or not value["cpu"]:
        raise ValueError("environment CPU is required")
    if not isinstance(value["os"], str) or not value["os"]:
        raise ValueError("environment OS is required")
    affinity = value["affinity"]
    if not isinstance(affinity, list) or any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in affinity
    ):
        raise ValueError("environment affinity is invalid")
    admission = value["admission"]
    if not isinstance(admission, dict):
        raise ValueError("environment admission is required")
    _require_exact_fields(admission, ADMISSION_FIELDS, "admission")
    if admission["accepted"] is not True:
        raise ValueError("environment admission was not accepted")
    for key in ADMISSION_FIELDS - {"accepted"}:
        if admission[key] is not None:
            require_finite_nonnegative(admission[key], key)


def _verify_run_timing(value: object) -> tuple[datetime, datetime]:
    if not isinstance(value, dict):
        raise ValueError("run timing must be an object")
    _require_exact_fields(value, RUN_TIMING_FIELDS, "run timing")
    started = _parse_utc(value["started_at"], "started_at")
    completed = _parse_utc(value["completed_at"], "completed_at")
    if completed < started:
        raise ValueError("run timing completion precedes start")
    if completed > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("run timing cannot be in the future")
    return started, completed


def _verify_corpus(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict):
        raise ValueError("corpus must be an object")
    _require_exact_fields(value, CORPUS_FIELDS, "corpus")
    if (
        not isinstance(value["manifest_name"], str)
        or not value["manifest_name"]
        or "/" in value["manifest_name"]
    ):
        raise ValueError("corpus manifest name must be a basename")
    if not SHA256_RE.fullmatch(str(value["manifest_sha256"])):
        raise ValueError("corpus manifest checksum must be SHA-256")
    # v1 is the retired generated corpus; v2 is the real-world one. Both are
    # readable so historical bundles stay verifiable, but only the pinned
    # canonical manifest may back a production bundle.
    if value["manifest_schema_version"] not in SAMPLE_FIELDS_BY_SCHEMA:
        raise ValueError("unsupported corpus manifest schema")
    schema_version = value["manifest_schema_version"]
    rows = value["samples"]
    if not isinstance(rows, list) or not rows or value["sample_count"] != len(rows):
        raise ValueError("corpus sample count is invalid")
    samples: dict[str, dict[str, object]] = {}
    paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("corpus sample must be an object")
        _require_exact_fields(row, SAMPLE_FIELDS_BY_SCHEMA[schema_version], "sample")
        sample_id = row["sample_id"]
        path = row["path"]
        if not isinstance(sample_id, str) or not sample_id or sample_id in samples:
            raise ValueError("corpus sample IDs must be unique strings")
        if not isinstance(path, str) or not _safe_relative_path(path) or path in paths:
            raise ValueError("corpus sample paths must be unique contained paths")
        if not SHA256_RE.fullmatch(str(row["sha256"])):
            raise ValueError("corpus sample checksum must be SHA-256")
        if (
            isinstance(row["byte_count"], bool)
            or not isinstance(row["byte_count"], int)
            or row["byte_count"] < 0
        ):
            raise ValueError("corpus sample byte count is invalid")
        for key in (
            "media_type",
            "size_class",
            "media_family",
            "source_ref",
            "license_id",
        ):
            if not isinstance(row[key], str) or not row[key]:
                raise ValueError(f"corpus sample {key} is required")
        if not isinstance(row["redistributable"], bool):
            raise ValueError("corpus redistributable flag must be boolean")
        samples[sample_id] = row
        paths.add(path)
    return samples


def _verify_canonical_corpus(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("production bundle requires the canonical corpus")
    if hash_file(CANONICAL_MANIFEST_PATH) != CANONICAL_MANIFEST_SHA256:
        raise ValueError("checked-in canonical manifest does not match its pinned digest")
    manifest = json.loads(CANONICAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = value["samples"]
    identities = tuple((row["sample_id"], row["path"]) for row in rows)
    if (
        value["manifest_name"] != CANONICAL_MANIFEST_PATH.name
        or value["manifest_sha256"] != CANONICAL_MANIFEST_SHA256
        or value["manifest_schema_version"] != manifest["schema_version"]
        or value["sample_count"] != len(CANONICAL_SAMPLE_IDENTITIES)
        or identities != CANONICAL_SAMPLE_IDENTITIES
        or rows != manifest["samples"]
    ):
        raise ValueError(
            "production bundle corpus does not match the canonical manifest and samples"
        )


def _verify_toolchain(
    value: object, codecs: tuple[str, ...] = PHASE_A_CODECS
) -> dict[str, dict[str, object]]:
    if not isinstance(value, list) or len(value) != len(codecs):
        raise ValueError("toolchain must contain exactly the phase's codecs")
    tools: dict[str, dict[str, object]] = {}
    for tool in value:
        if not isinstance(tool, dict):
            raise ValueError("tool provenance must be an object")
        _require_exact_fields(tool, TOOL_FIELDS, "tool provenance")
        name = tool["name"]
        if name not in codecs or name in tools:
            raise ValueError("toolchain codec is not uniquely allowlisted")
        for key in (
            "version",
            "binary_path",
            "binary_package",
            "binary_package_version",
            "source_package",
            "source_package_version",
            "upstream_source_reference",
        ):
            if not isinstance(tool[key], str) or not tool[key]:
                raise ValueError(f"tool {key} is required")
        for key in (
            "binary_sha256",
            "codec_build_provenance_sha256",
        ):
            if not SHA256_RE.fullmatch(str(tool[key])):
                raise ValueError(f"tool {key} must be SHA-256")
        if not CODE_SHA_RE.fullmatch(str(tool["upstream_release_sha"])):
            raise ValueError("tool upstream release SHA is invalid")
        if not isinstance(tool["flags"], list) or not all(
            isinstance(flag, str) and flag for flag in tool["flags"]
        ):
            raise ValueError("tool flags are invalid")
        capabilities = tool["capabilities"]
        if not isinstance(capabilities, dict):
            raise ValueError("tool capabilities must be an object")
        if name in CANDIDATE_CODECS:
            # The candidate is held to MORE than the incumbents, not less: it
            # must declare the profile it claims and pass the attribution gate
            # here as well as at run time, because a bundle can be verified long
            # after the run that produced it.
            required = {
                "whole_buffer_decode",
                "incremental_decode",
                "web_profile",
                "encode",
                "decode",
                "web_profile_version",
            }
            if set(capabilities) != required:
                raise ValueError("candidate capabilities are incomplete")
            if capabilities["whole_buffer_decode"] is not True:
                raise ValueError("candidate must declare whole-buffer decode")
            if not isinstance(capabilities["incremental_decode"], bool):
                raise ValueError("candidate incremental_decode must be boolean")
            validate_codec_attribution(name, capabilities)
        elif (
            set(capabilities) != {"whole_buffer_decode", "incremental_decode"}
            or capabilities["whole_buffer_decode"] is not True
            or capabilities["incremental_decode"] is not False
        ):
            raise ValueError("tool capabilities are invalid for Phase A")
        provenance_input = {
            key: tool[key]
            for key in (
                "name",
                "version",
                "binary_sha256",
                "flags",
                "binary_package",
                "binary_package_version",
                "source_package",
                "source_package_version",
                "upstream_release_sha",
                "upstream_source_reference",
            )
        }
        if stable_fingerprint(provenance_input) != tool["codec_build_provenance_sha256"]:
            raise ValueError("tool build provenance digest does not match its source fields")
        tools[name] = tool
    if tuple(sorted(tools)) != tuple(sorted(codecs)):
        raise ValueError("toolchain allowlist for this phase is incomplete")
    return tools


def _verify_protocol(
    value: object, codecs: tuple[str, ...] = PHASE_A_CODECS
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("protocol must be an object")
    _require_exact_fields(value, PROTOCOL_FIELDS, "protocol")
    if value["codecs"] != list(codecs):
        raise ValueError("protocol codec allowlist is invalid")
    trials_per_cell = value["trials_per_cell"]
    if (
        value["warmups"] != 3
        or isinstance(trials_per_cell, bool)
        or not isinstance(trials_per_cell, int)
        or trials_per_cell < 30
    ):
        raise ValueError("protocol requires exactly 3 warmups and at least 30 trials")
    if isinstance(value["randomized_order_seed"], bool) or not isinstance(
        value["randomized_order_seed"], int
    ):
        raise ValueError("protocol deterministic seed is invalid")
    if (
        isinstance(value["bootstrap_iterations"], bool)
        or not isinstance(value["bootstrap_iterations"], int)
        or value["bootstrap_iterations"] < 1
        or value["bootstrap_confidence"] != 0.95
    ):
        raise ValueError("protocol deterministic statistics are invalid")
    if value["network_isolation"] != "systemd_user_unit_plus_seccomp_network_deny":
        raise ValueError("protocol network isolation is invalid")
    if value["wall_clock"] != "time.monotonic_ns" or value["peak_rss"] != "gnu_time_verbose":
        raise ValueError("protocol instrumentation is invalid")
    for key in (
        "timeout_seconds",
        "max_input_bytes",
        "max_output_bytes",
        "max_expansion_ratio",
    ):
        if require_finite_nonnegative(value[key], key) <= 0:
            raise ValueError(f"protocol {key} must be positive")
    return value


def _verify_applicability(
    value: object, tools: dict[str, dict[str, object]] | None = None
) -> None:
    """The applicability block must match the toolchain, not a constant.

    time-to-first-decoded-byte is available exactly when some measured tool has
    an incremental decoder. Hardcoding False was correct while only Phase A
    existed and would have silently suppressed the one metric the candidate
    uniquely supports; hardcoding True would be worse, claiming a metric the
    incumbents cannot produce.
    """
    incremental = bool(tools) and any(
        tool["capabilities"].get("incremental_decode") is True
        for tool in tools.values()
    )
    expected = {
        "time_to_first_decoded_byte": {
            "available": incremental,
            "reason": (
                "an_incremental_decoder_is_present"
                if incremental
                else "phase_a_codecs_do_not_offer_incremental_decode"
            ),
        },
        "energy": {
            # Unconditional: RAPL counters are unreadable to the unprivileged
            # runner on every host this has run on, candidate or not.
            "available": False,
            "reason": "readable_calibrated_rapl_unavailable",
        },
    }
    if value != expected:
        raise ValueError("applicability declaration does not match the toolchain")


def _verify_trials(
    trials: list[object],
    samples: dict[str, dict[str, object]],
    tools: dict[str, dict[str, object]],
    protocol: dict[str, object],
    environment: dict[str, object],
    run_timing: tuple[datetime, datetime],
) -> None:
    seen: set[tuple[str, str, int]] = set()
    orders: set[int] = set()
    cell_trials: dict[tuple[str, str], set[int]] = defaultdict(set)
    environment_fingerprint = stable_fingerprint(environment)
    for trial in trials:
        if not isinstance(trial, dict):
            raise ValueError("trial must be an object")
        if not CODE_SHA_RE.fullmatch(str(trial.get("runner_code_sha", ""))):
            raise ValueError("trial code SHA is required")
        _require_exact_fields(trial, TRIAL_FIELDS, "trial")
        sample_id = trial["sample_id"]
        codec_key = trial["codec_key"]
        if sample_id not in samples or codec_key not in tools:
            raise ValueError("trial sample or codec is outside the closed bundle")
        if (
            isinstance(trial["trial_no"], bool)
            or not isinstance(trial["trial_no"], int)
            or not 1 <= trial["trial_no"] <= protocol["trials_per_cell"]
        ):
            raise ValueError("trial number is outside Phase A")
        key = (sample_id, codec_key, trial["trial_no"])
        if key in seen:
            raise ValueError("duplicate trial")
        seen.add(key)
        cell_trials[(sample_id, codec_key)].add(trial["trial_no"])
        order = trial["randomized_order"]
        if isinstance(order, bool) or not isinstance(order, int) or order < 1 or order in orders:
            raise ValueError("trial randomized order is invalid")
        orders.add(order)
        _verify_trial(
            trial,
            samples[sample_id],
            tools[codec_key],
            environment_fingerprint,
            environment["code_sha"],
            run_timing,
        )
    expected_trials = set(range(1, protocol["trials_per_cell"] + 1))
    for sample_id in samples:
        for codec_key in tools:
            if cell_trials[(sample_id, codec_key)] != expected_trials:
                raise ValueError(
                    "sample/codec cell requires the complete configured trial set: "
                    f"{sample_id}/{codec_key}"
                )
    expected_orders = set(
        range(1, len(samples) * len(tools) * protocol["trials_per_cell"] + 1)
    )
    if orders != expected_orders:
        raise ValueError("trial randomized order does not cover the complete schedule")


def _verify_trial(
    trial: dict[str, object],
    sample: dict[str, object],
    tool: dict[str, object],
    environment_fingerprint: str,
    runner_code_sha: str,
    run_timing: tuple[datetime, datetime],
) -> None:
    for key in (
        "codec_build_provenance_sha256",
        "environment_fingerprint",
        "tool_fingerprint",
        "tool_binary_sha256",
        "original_sha256",
        "compressed_sha256",
        "decoded_sha256",
    ):
        if not SHA256_RE.fullmatch(str(trial[key])):
            raise ValueError(f"trial {key} must be SHA-256")
    if not CODE_SHA_RE.fullmatch(str(trial["runner_code_sha"])):
        raise ValueError("trial code SHA is required")
    if trial["runner_code_sha"] != runner_code_sha:
        raise ValueError("trial code SHA is inconsistent")
    measured_at = _parse_utc(trial["measured_at"], "trial measured_at")
    if not run_timing[0] <= measured_at <= run_timing[1]:
        raise ValueError("trial measured_at is outside run timing")
    if (
        trial["environment_fingerprint"] != environment_fingerprint
        or trial["codec_build_provenance_sha256"]
        != tool["codec_build_provenance_sha256"]
        or trial["tool_fingerprint"] != stable_fingerprint(tool)
        or trial["tool_version"] != tool["version"]
        or trial["tool_binary_sha256"] != tool["binary_sha256"]
        or trial["tool_flags"] != tool["flags"]
    ):
        raise ValueError("trial provenance does not match the closed bundle")
    exact = (
        trial["roundtrip_exact"] is True
        and trial["original_sha256"] == trial["decoded_sha256"] == sample["sha256"]
        and trial["original_bytes"] == trial["decoded_bytes"] == sample["byte_count"]
    )
    if not exact:
        raise ValueError("trial round trip is not exact")
    for key in ("original_bytes", "compressed_bytes", "decoded_bytes"):
        if isinstance(trial[key], bool) or not isinstance(trial[key], int) or trial[key] < 0:
            raise ValueError(f"trial {key} is invalid")
    metrics = trial["metrics"]
    if not isinstance(metrics, dict) or set(metrics) != set(PHASE_A_METRICS):
        raise ValueError("trial metrics must be exactly the five Phase A metrics")
    for name in PHASE_A_METRICS:
        require_finite_nonnegative(metrics[name], name)
    if metrics["compressed_bytes"] != trial["compressed_bytes"]:
        raise ValueError("trial compressed byte metric is inconsistent")
    expected_ratio = (
        trial["compressed_bytes"] / trial["original_bytes"]
        if trial["original_bytes"]
        else 0.0
    )
    if not math.isclose(float(metrics["compression_ratio"]), expected_ratio, rel_tol=1e-12):
        raise ValueError("trial compression ratio is inconsistent")


def summarize_bundle(
    bundle: dict[str, object],
    *,
    seed: int = 74074,
    bootstrap_iterations: int = 5_000,
) -> dict[str, object]:
    candidate = copy.deepcopy(bundle)
    candidate["resource_summaries"] = []
    verify_bundle(candidate, require_summaries=False)
    return {
        "schema_version": 1,
        "scope": "resource_codec",
        "seed": seed,
        "bootstrap_iterations": bootstrap_iterations,
        "summaries": _summary_rows(
            candidate["resource_results"],
            seed=seed,
            bootstrap_iterations=bootstrap_iterations,
        ),
    }


def finalize_bundle(
    bundle: dict[str, object],
    *,
    seed: int = 74074,
    bootstrap_iterations: int = 5_000,
    require_canonical_corpus: bool = False,
) -> dict[str, object]:
    finalized = copy.deepcopy(bundle)
    finalized["protocol"]["randomized_order_seed"] = seed
    finalized["protocol"]["bootstrap_iterations"] = bootstrap_iterations
    finalized["protocol"]["bootstrap_confidence"] = 0.95
    finalized["resource_summaries"] = []
    verify_bundle(
        finalized,
        require_summaries=False,
        require_canonical_corpus=require_canonical_corpus,
    )
    finalized["resource_summaries"] = _summary_rows(
        finalized["resource_results"],
        seed=seed,
        bootstrap_iterations=bootstrap_iterations,
    )
    verify_bundle(
        finalized,
        require_summaries=True,
        require_canonical_corpus=require_canonical_corpus,
    )
    return finalized


def _summary_rows(
    trials: list[dict[str, object]],
    *,
    seed: int,
    bootstrap_iterations: int,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[tuple[int, float]]] = defaultdict(list)
    for trial in trials:
        for metric_name in PHASE_A_METRICS:
            grouped[(trial["sample_id"], trial["codec_key"], metric_name)].append(
                (trial["trial_no"], float(trial["metrics"][metric_name]))
            )
    rng = random.Random(seed)
    summaries = []
    for (sample_id, codec_key, metric_name), numbered_values in sorted(grouped.items()):
        numbered_values.sort()
        trial_numbers = [item[0] for item in numbered_values]
        values = [item[1] for item in numbered_values]
        median = statistics.median(values)
        bootstrapped = _bootstrap_medians(values, bootstrap_iterations, rng)
        summaries.append(
            {
                "sample_id": sample_id,
                "codec_key": codec_key,
                "metric_name": metric_name,
                "unit": RESOURCE_METRIC_UNITS[metric_name],
                "median": _clean_number(median),
                "p95": _clean_number(_nearest_rank(values, 0.95)),
                "bootstrap_95": {
                    "low": _clean_number(min(median, _nearest_rank(bootstrapped, 0.025))),
                    "high": _clean_number(max(median, _nearest_rank(bootstrapped, 0.975))),
                },
                "sample_count": len(values),
                "trial_numbers": trial_numbers,
                "values_sha256": stable_fingerprint(values),
            }
        )
    return summaries


def _bootstrap_medians(
    values: list[float],
    iterations: int,
    rng: random.Random,
) -> list[float]:
    if iterations <= 0:
        raise ValueError("bootstrap iterations must be positive")
    return [statistics.median(rng.choices(values, k=len(values))) for _ in range(iterations)]


def _nearest_rank(values: Iterable[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot rank an empty series")
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def _clean_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not path.is_absolute() and value not in {"", "."} and ".." not in path.parts


def _parse_utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{label} must be UTC")
    return parsed


def _require_exact_fields(value: dict[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise ValueError(f"{label} fields are not closed; unknown={unknown}, missing={missing}")


def load_fixture(path: Path) -> dict[str, object]:
    descriptor = json.loads(path.read_text(encoding="utf-8"))
    expected_fields = {
        "fixture_schema_version",
        "sample_id",
        "trial_count",
        "original_bytes",
        "compressed_start",
    }
    if not isinstance(descriptor, dict):
        raise ValueError("fixture descriptor must be an object")
    _require_exact_fields(descriptor, expected_fields, "fixture descriptor")
    if descriptor["fixture_schema_version"] != 1 or descriptor["trial_count"] != 30:
        raise ValueError("fixture requires schema version 1 and 30 trials")
    sample_id = descriptor["sample_id"]
    original_bytes = descriptor["original_bytes"]
    compressed_start = descriptor["compressed_start"]
    if not isinstance(sample_id, str) or not sample_id:
        raise ValueError("fixture sample ID is invalid")
    if (
        isinstance(original_bytes, bool)
        or not isinstance(original_bytes, int)
        or original_bytes <= 0
        or isinstance(compressed_start, bool)
        or not isinstance(compressed_start, int)
        or compressed_start < 0
    ):
        raise ValueError("fixture byte counts are invalid")
    environment = {
        "code_sha": "a" * 40,
        "cpu": "fixture-cpu",
        "os": "fixture-os",
        "affinity": [0],
        "admission": {
            "load_1m": 0.1,
            "load_per_cpu": 0.1,
            "max_load_per_cpu": 1.0,
            "temperature_c": 40.0,
            "max_temperature_c": 90,
            "accepted": True,
        },
    }
    sample = {
        "sample_id": sample_id,
        "path": f"payloads/{sample_id}.bin",
        "sha256": "c" * 64,
        "byte_count": original_bytes,
        "media_type": "application/octet-stream",
        "size_class": "small",
        "media_family": "binary",
        "source_ref": "project-authored:summary-fixture",
        "license_id": "MIT",
        "redistributable": True,
    }
    codec_flags = {
        "gzip": ["-9", "-c"],
        "brotli": ["--quality=11", "--stdout"],
        "zstd": ["-19", "--quiet", "--stdout"],
    }
    tools = []
    for codec in PHASE_A_CODECS:
        provenance = {
            "name": codec,
            "version": f"{codec} fixture",
            "binary_sha256": stable_fingerprint({"binary": codec}),
            "flags": codec_flags[codec],
            "binary_package": codec,
            "binary_package_version": "1.0-1",
            "source_package": codec,
            "source_package_version": "1.0-1",
            "upstream_release_sha": "b" * 40,
            "upstream_source_reference": (
                f"https://example.com/{codec}/commit/" + "b" * 40
            ),
        }
        tools.append(
            {
                **provenance,
                "binary_path": f"/usr/bin/{codec}",
                "capabilities": {
                    "whole_buffer_decode": True,
                    "incremental_decode": False,
                },
                "codec_build_provenance_sha256": stable_fingerprint(provenance),
            }
        )
    trials = []
    order = 0
    for trial_no in range(1, 31):
        for tool in tools:
            order += 1
            compressed_bytes = compressed_start + trial_no - 1
            trials.append(
                {
                    "sample_id": sample_id,
                    "codec_key": tool["name"],
                    "trial_no": trial_no,
                    "randomized_order": order,
                    "measured_at": "2026-01-01T00:00:30Z",
                    "runner_code_sha": environment["code_sha"],
                    "codec_build_provenance_sha256": tool[
                        "codec_build_provenance_sha256"
                    ],
                    "environment_fingerprint": stable_fingerprint(environment),
                    "tool_fingerprint": stable_fingerprint(tool),
                    "tool_version": tool["version"],
                    "tool_binary_sha256": tool["binary_sha256"],
                    "tool_flags": tool["flags"],
                    "original_sha256": sample["sha256"],
                    "compressed_sha256": f"{order:064x}",
                    "decoded_sha256": sample["sha256"],
                    "original_bytes": original_bytes,
                    "compressed_bytes": compressed_bytes,
                    "decoded_bytes": original_bytes,
                    "roundtrip_exact": True,
                    "metrics": {
                        "compressed_bytes": compressed_bytes,
                        "compression_ratio": compressed_bytes / original_bytes,
                        "compression_duration": trial_no,
                        "decompression_duration": trial_no / 2,
                        "peak_memory": 4096,
                    },
                }
            )
    return {
        "schema_version": 1,
        "scope": "resource_codec",
        "phase": "A",
        "run_timing": {
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:01:00Z",
        },
        "corpus": {
            "manifest_name": "fixture.v1.json",
            "manifest_sha256": stable_fingerprint(descriptor),
            "manifest_schema_version": 1,
            "sample_count": 1,
            "samples": [sample],
        },
        "toolchain": tools,
        "protocol": {
            "codecs": list(PHASE_A_CODECS),
            "warmups": 3,
            "trials_per_cell": 30,
            "randomized_order_seed": 74074,
            "bootstrap_iterations": 5_000,
            "bootstrap_confidence": 0.95,
            "timeout_seconds": 60,
            "max_input_bytes": 2 * 1024 * 1024,
            "max_output_bytes": 64 * 1024 * 1024,
            "max_expansion_ratio": 64,
            "network_isolation": "systemd_user_unit_plus_seccomp_network_deny",
            "wall_clock": "time.monotonic_ns",
            "peak_rss": "gnu_time_verbose",
        },
        "environment": environment,
        "applicability": {
            "time_to_first_decoded_byte": {
                "available": False,
                "reason": "phase_a_codecs_do_not_offer_incremental_decode",
            },
            "energy": {
                "available": False,
                "reason": "readable_calibrated_rapl_unavailable",
            },
        },
        "resource_results": trials,
        "resource_summaries": [],
        "page_results": {
            "explicit_wasm_application": [],
            "transparent_http_page": [],
        },
    }


def _atomic_write_json(path: Path, value: dict[str, object]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", type=Path)
    source.add_argument("--bundle", type=Path)
    parser.add_argument("--seed", type=int, default=74074)
    parser.add_argument("--bootstrap-iterations", type=int, default=5_000)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    path = args.bundle if args.bundle is not None else args.fixture
    bundle = (
        json.loads(path.read_text(encoding="utf-8"))
        if args.bundle is not None
        else load_fixture(path)
    )
    finalized = finalize_bundle(
        bundle,
        seed=args.seed,
        bootstrap_iterations=args.bootstrap_iterations,
        require_canonical_corpus=args.bundle is not None,
    )
    if args.bundle is not None:
        _atomic_write_json(path, finalized)
        verified = json.loads(path.read_text(encoding="utf-8"))
        verify_bundle(
            verified,
            require_summaries=True,
            require_canonical_corpus=True,
        )
        print(
            json.dumps(
                {
                    "bundle": str(path),
                    "resource_results": len(verified["resource_results"]),
                    "resource_summaries": len(verified["resource_summaries"]),
                },
                sort_keys=True,
            )
        )
    else:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "scope": "resource_codec",
                    "seed": args.seed,
                    "bootstrap_iterations": args.bootstrap_iterations,
                    "summaries": finalized["resource_summaries"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
