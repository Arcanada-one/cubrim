"""
pytest fixtures: corpus loader and synthetic generators.
Fixed seed for reproducibility (numpy.random with explicit seed).
"""
import os
import hashlib
import numpy as np
import pytest

# Fixed seed — reproducible corpus across runs
_RNG = np.random.default_rng(42)


def _make_text_sample() -> bytes:
    """~1 KB of repeated ASCII text (log-like lines)."""
    line = b"2026-06-17T12:00:00Z INFO cubrim prototype starting up level=debug\n"
    count = (1024 // len(line)) + 1
    return (line * count)[:1024]


def _make_random_sample(size: int = 1024) -> bytes:
    """Uniformly random bytes with fixed seed — worst case for compression."""
    rng = np.random.default_rng(123)
    return rng.integers(0, 256, size=size, dtype=np.uint8).tobytes()


def _make_log_blob(size: int = 16 * 1024) -> bytes:
    """
    ~16 KB realistic log blob: JSON-like lines with repeated field names
    plus occasional binary noise. Simulates a log segment.
    """
    templates = [
        b'{"ts":"2026-06-17T12:00:00Z","level":"INFO","msg":"request processed","latency_ms":42}\n',
        b'{"ts":"2026-06-17T12:00:01Z","level":"DEBUG","msg":"cache hit","key":"user:1234"}\n',
        b'{"ts":"2026-06-17T12:00:02Z","level":"WARN","msg":"slow query","duration_ms":512}\n',
        b'{"ts":"2026-06-17T12:00:03Z","level":"ERROR","msg":"connection timeout","host":"db-1"}\n',
    ]
    buf = bytearray()
    rng = np.random.default_rng(99)
    while len(buf) < size:
        line = templates[rng.integers(len(templates))]
        buf.extend(line)
    return bytes(buf[:size])


def _make_larger_text(size: int = 64 * 1024) -> bytes:
    """64 KB of English-like repeated text for ratio/locality corpus."""
    fragment = (
        b"the quick brown fox jumps over the lazy dog "
        b"pack my box with five dozen liquor jugs "
        b"how vexingly quick daft zebras jump "
    )
    repetitions = (size // len(fragment)) + 1
    return (fragment * repetitions)[:size]


def _make_larger_random(size: int = 64 * 1024) -> bytes:
    """64 KB uniform random bytes — worst case for compression ratio."""
    rng = np.random.default_rng(777)
    return rng.integers(0, 256, size=size, dtype=np.uint8).tobytes()


@pytest.fixture
def small_text_bytes() -> bytes:
    return _make_text_sample()


@pytest.fixture
def small_random_bytes() -> bytes:
    return _make_random_sample(1024)


@pytest.fixture
def log_blob_bytes() -> bytes:
    return _make_log_blob(16 * 1024)


@pytest.fixture
def round_trip_corpus() -> list[tuple[str, bytes]]:
    """≥3 samples for AC-1 round-trip testing."""
    return [
        ("text_1kb", _make_text_sample()),
        ("random_1kb", _make_random_sample(1024)),
        ("log_16kb", _make_log_blob(16 * 1024)),
    ]


@pytest.fixture
def locality_corpus() -> list[tuple[str, bytes]]:
    """≥3 files ≥100 KB total for AC-3/AC-4 locality and ratio measurements."""
    return [
        ("text_64kb", _make_larger_text(64 * 1024)),
        ("random_64kb", _make_larger_random(64 * 1024)),
        ("log_16kb", _make_log_blob(16 * 1024)),
    ]


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
