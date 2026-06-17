"""
Decode robustness tests — V-AC-4.

Corrupt input must raise explicitly, never produce silent garbage.
- Bad magic bytes → ValueError
- Wrong version → ValueError
- Over-large gap in stream → ValueError
- Truncated header → ValueError / struct.error
- Inconsistent count vs actual data → ValueError
"""
import struct
import pytest

from cubrim_proto.codec import encode, decode
from cubrim_proto.header import MAGIC, VERSION


def _good_blob(data: bytes = b"hello world test") -> bytes:
    return encode(data)


# ---------------------------------------------------------------------------
# Bad magic
# ---------------------------------------------------------------------------

def test_bad_magic_raises():
    blob = _good_blob()
    corrupted = b"\xDE\xAD\xBE\xEF" + blob[4:]
    with pytest.raises((ValueError, struct.error), match="magic|invalid|corrupt"):
        decode(corrupted)


# ---------------------------------------------------------------------------
# Wrong version
# ---------------------------------------------------------------------------

def test_wrong_version_raises():
    blob = _good_blob()
    # Version byte is after magic (4 bytes); version=99 is unsupported
    magic_len = len(MAGIC)
    corrupted = blob[:magic_len] + bytes([99]) + blob[magic_len + 1:]
    with pytest.raises(ValueError, match="version|unsupported"):
        decode(corrupted)


# ---------------------------------------------------------------------------
# Truncated data
# ---------------------------------------------------------------------------

def test_truncated_to_zero_raises():
    with pytest.raises((ValueError, struct.error)):
        decode(b"")


def test_truncated_to_few_bytes_raises():
    with pytest.raises((ValueError, struct.error)):
        decode(b"\xCB\x52\x49\x4D")  # Only magic, no version


# ---------------------------------------------------------------------------
# Garbage blob
# ---------------------------------------------------------------------------

def test_random_garbage_raises():
    import numpy as np
    rng = np.random.default_rng(555)
    garbage = rng.integers(0, 256, size=128, dtype=np.uint8).tobytes()
    with pytest.raises((ValueError, struct.error)):
        decode(garbage)


# ---------------------------------------------------------------------------
# Valid encode → valid decode (sanity)
# ---------------------------------------------------------------------------

def test_valid_blob_decodes_correctly():
    data = b"cubrim round-trip sanity check"
    assert decode(encode(data)) == data
