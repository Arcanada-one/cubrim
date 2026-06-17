"""
Round-trip property test — CORNERSTONE GATE (V-AC-1).

sha256(S) == sha256(decode(encode(S))) for every corpus file.
A single counterexample is failure. No exceptions.

Also verifies the R3.1 worked example from rulebook v1:
  populated {0, 3, 7} with b_1=8
  encode → D = (1, 3, 4)
  decode → x: -1+1=0, 0+3=3, 3+4=7 → {0, 3, 7}
"""
import hashlib

import pytest

from cubrim_proto.codec import encode, decode
from cubrim_proto.distance_map import encode_axis_gaps, decode_axis_gaps


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# R3.1 worked example (rulebook §3.1 truth table, PRD §4.7)
# ---------------------------------------------------------------------------

def test_r3_1_worked_example_gap_encoding():
    """
    Rulebook R3.1 worked example: populated set {0, 3, 7} with b_k=8.
    encode → D = (1, 3, 4)
    Verify sentinel-1 start and gap=1 means zero skipped slots.
    """
    coords = [0, 3, 7]
    b_k = 8
    gaps = encode_axis_gaps(coords, b_k)
    assert gaps == [1, 3, 4], f"Expected [1, 3, 4], got {gaps}"


def test_r3_1_worked_example_gap_decoding():
    """
    Rulebook R3.1: decode D=(1,3,4) back to {0,3,7}.
    Decode: x starts at -1; -1+1=0, 0+3=3, 3+4=7.
    """
    gaps = [1, 3, 4]
    coords = decode_axis_gaps(gaps)
    assert coords == [0, 3, 7], f"Expected [0, 3, 7], got {coords}"


def test_r3_1_gap1_means_zero_skipped():
    """gap=1 means immediately adjacent — zero skipped slots."""
    # populated at 0, 1, 2 (no gaps between them)
    coords = [0, 1, 2]
    b_k = 4
    gaps = encode_axis_gaps(coords, b_k)
    assert gaps == [1, 1, 1], f"gap=1 must mean no skip; got {gaps}"
    assert decode_axis_gaps(gaps) == [0, 1, 2]


def test_r3_1_first_element_at_slot_0():
    """First populated slot = 0 → gap = -1 + 1 = 0 is the coord; gap encoded = 1."""
    coords = [0]
    gaps = encode_axis_gaps(coords, b_k=8)
    assert gaps == [1]
    assert decode_axis_gaps(gaps) == [0]


def test_r3_1_first_element_at_slot_3():
    """First populated slot = 3 → gap = 3 - (-1) = 4, NOT 3."""
    coords = [3]
    gaps = encode_axis_gaps(coords, b_k=8)
    assert gaps == [4], f"Expected [4], got {gaps}"
    assert decode_axis_gaps(gaps) == [3]


# ---------------------------------------------------------------------------
# Full round-trip on corpus
# ---------------------------------------------------------------------------

def test_round_trip_corpus(round_trip_corpus):
    """
    V-AC-1 cornerstone: sha256(S) == sha256(decode(encode(S))) for every
    corpus file. A single counterexample is a hard failure.
    """
    failures = []
    for name, data in round_trip_corpus:
        blob = encode(data)
        recovered = decode(blob)
        orig_hash = sha256_of(data)
        recv_hash = sha256_of(recovered)
        if orig_hash != recv_hash:
            failures.append(
                f"ROUND-TRIP FAILURE on '{name}': "
                f"orig={orig_hash[:12]} recovered={recv_hash[:12]}"
            )
        if len(recovered) != len(data):
            failures.append(
                f"LENGTH MISMATCH on '{name}': "
                f"orig={len(data)} recovered={len(recovered)}"
            )

    assert not failures, "\n".join(failures)


def test_round_trip_empty_input():
    """Edge case: empty byte string must round-trip cleanly."""
    data = b""
    assert decode(encode(data)) == data


def test_round_trip_single_byte():
    """Edge case: single byte."""
    data = b"\x42"
    assert decode(encode(data)) == data


def test_round_trip_all_same_byte():
    """All same byte — maximally compressible."""
    data = b"\xAA" * 256
    assert decode(encode(data)) == data


def test_round_trip_all_distinct_bytes():
    """All 256 distinct values — least compressible with cube mode."""
    data = bytes(range(256))
    assert decode(encode(data)) == data
