"""Data contracts and trust-boundary helpers for the web benchmark runner."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PHASE_A_TRIALS = 30
PHASE_A_WARMUPS = 3
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CODE_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


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

    def __post_init__(self) -> None:
        if not IDENTIFIER_RE.fullmatch(self.sample_id):
            raise ValueError("sample_id contains unsafe characters")
        if not SHA256_RE.fullmatch(self.sha256):
            raise ValueError("sample SHA-256 must be 64 lowercase hex characters")
        if self.byte_count < 0:
            raise ValueError("sample byte_count must be nonnegative")


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
    runner_code_sha: str
    codec_code_sha: str
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
        for code_sha in (self.runner_code_sha, self.codec_code_sha):
            if not CODE_SHA_RE.fullmatch(code_sha):
                raise ValueError("trial code SHA must be 40 or 64 lowercase hex characters")
        for digest in (
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


def stable_fingerprint(value: object) -> str:
    import json

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
