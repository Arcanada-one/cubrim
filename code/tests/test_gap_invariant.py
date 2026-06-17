"""
Gap invariant fail-closed tests — R3.1.

Invariant: 1 <= gap_k <= b_k <= B
- gap=0 is forbidden (two points cannot share a slot on an axis)
- gap>b_k is forbidden (skip cannot exceed edge length)
Both cases must raise, never silently truncate or corrupt.
"""
import pytest

from cubrim_proto.distance_map import encode_axis_gaps, decode_axis_gaps, validate_gaps


# ---------------------------------------------------------------------------
# Fail-closed: gap=0 must raise
# ---------------------------------------------------------------------------

def test_gap_zero_forbidden_on_encode():
    """
    If the same coord appears twice, encode must raise (gap=0 case).
    Two populated points at the same position on an axis = encoder bug.
    """
    # Duplicate coord → gap=0 would result
    with pytest.raises(ValueError, match="gap"):
        encode_axis_gaps([0, 0], b_k=4)


def test_validate_gaps_rejects_zero():
    """validate_gaps([0]) must raise ValueError."""
    with pytest.raises(ValueError, match="gap"):
        validate_gaps([0], b_k=4)


# ---------------------------------------------------------------------------
# Fail-closed: gap>b_k must raise
# ---------------------------------------------------------------------------

def test_gap_exceeds_bk_on_encode():
    """
    Coord outside [0, b_k-1] range causes gap > b_k.
    Encoder must detect this and raise.
    """
    # coord=5 with b_k=4 is out of range → gap from -1 = 6 > b_k=4
    with pytest.raises(ValueError, match="gap|coord|bound"):
        encode_axis_gaps([5], b_k=4)


def test_validate_gaps_rejects_exceeds_bk():
    """validate_gaps with a gap > b_k must raise."""
    with pytest.raises(ValueError, match="gap|bound"):
        validate_gaps([5], b_k=4)


# ---------------------------------------------------------------------------
# Fail-closed: non-monotone coords must raise
# ---------------------------------------------------------------------------

def test_non_monotone_coords_raise():
    """
    Coordinates must be strictly increasing (sorted ascending).
    Non-monotone → gap would be ≤0.
    """
    with pytest.raises(ValueError, match="gap|monotone|order|sorted"):
        encode_axis_gaps([3, 1], b_k=8)


# ---------------------------------------------------------------------------
# Truth-table boundary cases
# ---------------------------------------------------------------------------

def test_gap_equals_bk_is_valid():
    """
    Gap exactly equal to b_k is the maximum valid gap.
    Populated at last slot (b_k-1) from sentinel -1.
    """
    b_k = 8
    # Only element at index 7 → gap = 7 - (-1) = 8 = b_k → valid
    coords = [b_k - 1]
    gaps = encode_axis_gaps(coords, b_k)
    assert gaps == [b_k], f"Expected [{b_k}], got {gaps}"
    assert decode_axis_gaps(gaps) == [b_k - 1]


def test_gap_exactly_1_is_valid():
    """gap=1 is the minimum and means zero skipped slots."""
    gaps = [1, 1, 1]
    b_k = 5
    validate_gaps(gaps, b_k)  # must NOT raise
    assert decode_axis_gaps(gaps) == [0, 1, 2]


def test_validate_gaps_accepts_valid_sequence():
    """A well-formed gap sequence must pass validation."""
    # {0, 3, 7} → gaps (1, 3, 4) with b_k=8
    validate_gaps([1, 3, 4], b_k=8)  # must not raise


# ---------------------------------------------------------------------------
# Roundtrip invariance check
# ---------------------------------------------------------------------------

def test_encode_decode_roundtrip_preserves_coords():
    """encode then decode restores the original coordinate list."""
    for coords in ([0, 1, 5, 7], [0], [3, 7], [0, 1, 2, 3, 4, 5]):
        b_k = 16
        gaps = encode_axis_gaps(coords, b_k)
        recovered = decode_axis_gaps(gaps)
        assert recovered == coords, f"Failed for coords={coords}: got {recovered}"
