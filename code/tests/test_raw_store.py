"""
Raw-store fallback tests — AC-2, R7.

R7: if size(cube) >= size(raw) + header_overhead → mode=1 (raw-store).
On ~1 MB uniform-random bytes the cube mode always bloats → raw-store MUST engage.
Output size must be <= size(S) + HEADER_OVERHEAD_BOUND (target <=1.05x, hard limit 1.1x).
"""
import numpy as np
import pytest

from cubrim_proto.codec import encode, decode, HEADER_OVERHEAD_BOUND
from cubrim_proto.header import parse_header


RANDOM_1MB_SEED = 42


def make_random_mb(seed: int = RANDOM_1MB_SEED) -> bytes:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=1_048_576, dtype=np.uint8).tobytes()


# ---------------------------------------------------------------------------
# R7 fires on random data
# ---------------------------------------------------------------------------

def test_raw_store_engages_on_random_data():
    """
    1 MB uniform-random bytes: cube mode would expand (near-uniform gap distribution).
    R7 raw-store must engage → mode field in header = 1.
    """
    data = make_random_mb()
    blob = encode(data)
    hdr, _ = parse_header(blob)
    assert hdr["mode"] == 1, (
        f"Expected mode=1 (raw-store) for random input, got mode={hdr['mode']}. "
        "R7 fallback did not fire — encoder bug."
    )


def test_raw_store_output_size_bounded():
    """
    R7 guarantee: output <= size(S) + HEADER_OVERHEAD_BOUND.
    Hard limit: ratio <= 1.1x. Target: <= 1.05x.
    """
    data = make_random_mb()
    blob = encode(data)
    max_allowed = len(data) + HEADER_OVERHEAD_BOUND
    assert len(blob) <= max_allowed, (
        f"Output size {len(blob)} exceeds bound {max_allowed} "
        f"(input={len(data)}, HEADER_OVERHEAD_BOUND={HEADER_OVERHEAD_BOUND}). "
        "R7 overhead constant is too large or raw-store not firing."
    )
    ratio = len(blob) / len(data)
    assert ratio <= 1.1, (
        f"Ratio {ratio:.4f} > 1.1 — R7 not bounding expansion properly."
    )


def test_raw_store_round_trip():
    """R7 raw-store output must still round-trip correctly."""
    data = make_random_mb()
    blob = encode(data)
    recovered = decode(blob)
    assert recovered == data, "Raw-store round-trip failed"


# ---------------------------------------------------------------------------
# Smaller random inputs
# ---------------------------------------------------------------------------

def test_raw_store_small_random():
    """256-byte uniform random: raw-store should fire (cube can't compress)."""
    rng = np.random.default_rng(88)
    data = rng.integers(0, 256, size=256, dtype=np.uint8).tobytes()
    blob = encode(data)
    # Round-trip must hold regardless of mode
    assert decode(blob) == data


def test_raw_store_overhead_bound_constant():
    """
    HEADER_OVERHEAD_BOUND must be <= 512 bytes.
    v1 header max size: fixed(13)+count(4)+b_k(2)+schemes(3)+n_distinct(2)+
    inverse_dict(256)+traversal_phi(2)+gap_counts(4) = 286 bytes.
    We allow 512 as the upper acceptability limit; actual bound is 320.
    """
    assert HEADER_OVERHEAD_BOUND <= 512, (
        f"HEADER_OVERHEAD_BOUND={HEADER_OVERHEAD_BOUND} exceeds 512 B acceptability limit"
    )
    # Confirm it is not unnecessarily large (would defeat R7 guarantee on small inputs)
    assert HEADER_OVERHEAD_BOUND <= 1024, (
        f"HEADER_OVERHEAD_BOUND={HEADER_OVERHEAD_BOUND} is unreasonably large"
    )
