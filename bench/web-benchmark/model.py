"""Data contracts and trust-boundary helpers for the web benchmark runner."""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PHASE_A_TRIALS = 30
PHASE_A_WARMUPS = 3
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CODE_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]+$")
CANONICAL_KEY_RE = re.compile(r"^[\x20-\x7e]+$")
MAX_SAFE_INTEGER = (1 << 53) - 1
FLOAT64_TAG = "$float64"
CANONICAL_FINGERPRINT_CONTRACT = "cubrim-canonical-json-v1"


class RoundTripError(ValueError):
    """Raised when decoded bytes are not bit-identical to the source."""


@dataclass(frozen=True)
class BenchmarkSample:
    sample_id: str
    path: str
    sha256: str
    byte_count: int
    media_type: str
    size_class: str
    media_family: str = "fixture"
    source_ref: str = "inline-fixture"
    license_id: str = "NOASSERTION"
    redistributable: bool = False

    def __post_init__(self) -> None:
        if not IDENTIFIER_RE.fullmatch(self.sample_id):
            raise ValueError("sample_id contains unsafe characters")
        if not SHA256_RE.fullmatch(self.sha256):
            raise ValueError("sample SHA-256 must be 64 lowercase hex characters")
        if self.byte_count < 0:
            raise ValueError("sample byte_count must be nonnegative")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.path,
                self.media_type,
                self.size_class,
                self.media_family,
                self.source_ref,
                self.license_id,
            )
        ):
            raise ValueError("sample provenance fields must be non-empty strings")
        if not isinstance(self.redistributable, bool):
            raise ValueError("sample redistributable must be boolean")

    def as_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunnerConfig:
    trials: int = PHASE_A_TRIALS
    warmups: int = PHASE_A_WARMUPS
    timeout_seconds: float = 60.0
    max_input_bytes: int = 2 * 1024 * 1024
    max_output_bytes: int = 64 * 1024 * 1024
    max_expansion_ratio: float = 64.0
    random_seed: int = 74074

    def __post_init__(self) -> None:
        if self.trials < PHASE_A_TRIALS:
            raise ValueError("Phase A requires at least 30 valid trials per cell")
        if self.warmups != PHASE_A_WARMUPS:
            raise ValueError(f"Phase A warmups are fixed at {PHASE_A_WARMUPS}")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        if min(self.max_input_bytes, self.max_output_bytes) <= 0:
            raise ValueError("size limits must be positive")
        if self.max_expansion_ratio <= 0:
            raise ValueError("expansion ratio limit must be positive")


@dataclass(frozen=True)
class TrialRecord:
    sample_id: str
    codec_key: str
    trial_no: int
    randomized_order: int
    measured_at: str
    runner_code_sha: str
    codec_build_provenance_sha256: str
    environment_fingerprint: str
    tool_fingerprint: str
    tool_version: str
    tool_binary_sha256: str
    tool_flags: tuple[str, ...]
    original_sha256: str
    compressed_sha256: str
    decoded_sha256: str
    original_bytes: int
    compressed_bytes: int
    decoded_bytes: int
    roundtrip_exact: bool
    metrics: dict[str, float | int]

    def __post_init__(self) -> None:
        if not CODE_SHA_RE.fullmatch(self.runner_code_sha):
            raise ValueError("runner code SHA must be 40 or 64 lowercase hex characters")
        for digest in (
            self.codec_build_provenance_sha256,
            self.tool_binary_sha256,
            self.original_sha256,
            self.compressed_sha256,
            self.decoded_sha256,
        ):
            if not SHA256_RE.fullmatch(digest):
                raise ValueError("trial content hashes must be SHA-256")
        if not self.roundtrip_exact:
            raise RoundTripError("round trip is not exact")
        if self.original_sha256 != self.decoded_sha256:
            raise RoundTripError("decoded hash does not match original")
        if self.original_bytes != self.decoded_bytes:
            raise RoundTripError("decoded size does not match original")
        expected_metrics = {
            "compressed_bytes",
            "compression_ratio",
            "compression_duration",
            "decompression_duration",
            "peak_memory",
        }
        if set(self.metrics) != expected_metrics:
            raise ValueError("Phase A trial metrics must be exactly the required five metrics")
        for name, value in self.metrics.items():
            require_finite_nonnegative(value, name)

    def as_json(self) -> dict[str, Any]:
        value = asdict(self)
        value["tool_flags"] = list(self.tool_flags)
        return value


def hash_file(path: Path, *, max_bytes: int | None = None) -> str:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise ValueError("input exceeds configured maximum")
            digest.update(chunk)
    return digest.hexdigest()


def resolve_contained(root: Path, relative: str) -> Path:
    root_resolved = root.resolve(strict=True)
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError("path must be contained beneath the corpus root")
    try:
        resolved = (root_resolved / candidate).resolve(strict=True)
        resolved.relative_to(root_resolved)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise ValueError("path must be contained beneath the corpus root") from exc
    if not resolved.is_file():
        raise ValueError("contained payload must be a regular file")
    return resolved


def enforce_size_limits(
    input_bytes: int,
    output_bytes: int,
    *,
    max_input_bytes: int,
    max_output_bytes: int,
    max_expansion_ratio: float,
) -> None:
    if input_bytes > max_input_bytes:
        raise ValueError("input exceeds configured maximum")
    if output_bytes > max_output_bytes:
        raise ValueError("output exceeds configured maximum")
    if input_bytes == 0:
        if output_bytes:
            raise ValueError("expansion exceeds configured ratio")
        return
    if output_bytes / input_bytes > max_expansion_ratio:
        raise ValueError("expansion exceeds configured ratio")


def require_finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    if number < 0:
        raise ValueError(f"{label} must be nonnegative")
    return number


def canonical_json_bytes(value: object) -> bytes:
    """Encode the cross-runtime ``cubrim-canonical-json-v1`` contract.

    Object keys are printable ASCII, reserved ``$float64`` is rejected, and
    keys are sorted lexically. Safe integers remain JSON numbers. Integral
    finite floats normalize to safe integers; other finite floats normalize to
    ``{"$float64": "<big-endian IEEE-754 binary64 hex>"}``. Arrays preserve
    order, strings use UTF-8 without ASCII escaping, and unsupported,
    nonfinite, or JavaScript-unsafe values fail closed.
    """

    normalized = _canonical_value(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_value(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("canonical strings must be valid UTF-8") from exc
        return value
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("canonical integers must be JavaScript-safe")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical floats must be finite")
        if value.is_integer():
            integer = int(value)
            if abs(integer) > MAX_SAFE_INTEGER:
                raise ValueError("canonical integral floats must be JavaScript-safe")
            return integer
        return {FLOAT64_TAG: struct.pack(">d", value).hex()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        keys = list(value)
        if any(
            not isinstance(key, str)
            or not CANONICAL_KEY_RE.fullmatch(key)
            or key == FLOAT64_TAG
            for key in keys
        ):
            raise ValueError(
                "canonical object keys must be printable ASCII and not reserved"
            )
        normalized = {}
        for key in sorted(keys):
            normalized[key] = _canonical_value(value[key])
        return normalized
    raise ValueError(f"unsupported canonical value type: {type(value).__name__}")


def stable_fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
