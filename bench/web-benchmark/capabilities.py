"""Closed capability gates for benchmark attribution and optional metrics."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Iterable, Mapping


# Phase A compares the presets real web transport actually uses, not only the
# archival ones. A CDN serving dynamic responses runs brotli-5 or zstd-3; the
# maximum settings appear on precompressed static assets. Measuring only
# brotli-11/gzip-9/zstd-19 flatters any candidate on speed and understates the
# ratio it has to beat, which is the bias CUBR-0068 warned about.
PHASE_A_CODECS = ("gzip-9", "brotli-11", "brotli-5", "zstd-19", "zstd-3")

# The candidate channel is deliberately a separate tuple. Cubrim-Web is our own
# codec measured against the five above; folding it into PHASE_A_CODECS would
# silently redefine what every existing bundle, canonical fingerprint and
# database row means, and would let a self-comparison inherit the incumbents'
# provenance contract, which it cannot satisfy — it has no distro package.
CANDIDATE_CODECS = ("cubrim-web",)


def validate_codec_attribution(codec_name: str, capabilities: Mapping[str, object]) -> None:
    normalized = codec_name.casefold().replace("_", "-")
    if normalized != "cubrim-web":
        return
    version = capabilities.get("web_profile_version")
    has_real_profile = (
        capabilities.get("web_profile") is True
        and capabilities.get("encode") is True
        and capabilities.get("decode") is True
        and isinstance(version, str)
        and bool(version.strip())
        and version.casefold() not in {"pending", "planned", "placeholder"}
    )
    if not has_real_profile:
        raise ValueError("Cubrim-Web attribution requires a real Web Profile capability")


def require_phase_a_codec(codec_name: str) -> None:
    if codec_name not in PHASE_A_CODECS:
        raise ValueError(f"Phase A codec is not allowlisted: {codec_name}")


def require_candidate_codec(codec_name: str) -> None:
    if codec_name in PHASE_A_CODECS:
        raise ValueError(
            f"{codec_name} is a published Phase A incumbent, not a candidate"
        )
    if codec_name not in CANDIDATE_CODECS:
        raise ValueError(f"candidate codec is not allowlisted: {codec_name}")


def first_decoded_byte_ms(
    incremental_decode: bool,
    first_input_ns: int,
    output_chunks: Iterable[tuple[int, bytes]],
) -> float:
    if not incremental_decode:
        raise ValueError("first decoded byte requires an incremental decoder")
    for observed_ns, chunk in output_chunks:
        if chunk:
            if observed_ns < first_input_ns:
                raise ValueError("output timestamp precedes first input")
            return (observed_ns - first_input_ns) / 1_000_000
    raise ValueError("first decoded byte requires non-empty incremental output")


def energy_capability(
    counter_path: Path,
    calibration: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if calibration is None or not counter_path.is_file() or not os.access(counter_path, os.R_OK):
        return None
    baseline = calibration.get("baseline_joules")
    duration = calibration.get("batch_duration_ms")
    if (
        isinstance(baseline, bool)
        or not isinstance(baseline, (int, float))
        or not math.isfinite(float(baseline))
        or float(baseline) < 0
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(float(duration))
        or float(duration) <= 0
    ):
        return None
    try:
        initial = int(counter_path.read_text(encoding="ascii").strip())
    except (OSError, UnicodeError, ValueError):
        return None
    if initial < 0:
        return None
    return {
        "counter_path": str(counter_path),
        "initial_energy_uj": initial,
        "baseline_joules": float(baseline),
        "batch_duration_ms": float(duration),
    }
