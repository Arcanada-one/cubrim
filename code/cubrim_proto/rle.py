"""
Cubrim prototype — pure RLE encoding of gap streams.

# R4: Compact run-encoding of the distance map (v1-default: pure RLE).

Each gap stream is encoded as a sequence of (value, run_length) pairs.
Trivially reversible, zero decode ambiguity.

v1-default: simple RLE with (value: uint16, run_length: uint16) pairs.
Run-length capped at 65535 to fit uint16.

Resolution criterion (OQ-2): a scheme minimising bits-per-populated-point on the
corpus beats this baseline (challengers: RLE+Huffman, Golomb-Rice, ANS).
"""

import struct
from typing import Iterator


# Pack format for one RLE pair: (value, run_length) both as 2-byte unsigned
_PAIR_STRUCT = struct.Struct(">HH")  # big-endian uint16 x 2
PAIR_SIZE = _PAIR_STRUCT.size        # 4 bytes per pair
MAX_RUN = 65535


def rle_encode(gaps: list[int]) -> bytes:
    """
    R4: Encode a list of gap values as pure RLE.
    Returns bytes: sequence of (value: u16, run_length: u16) pairs.
    """
    if not gaps:
        return b""

    pairs: list[tuple[int, int]] = []
    current = gaps[0]
    run = 1

    for g in gaps[1:]:
        if g == current and run < MAX_RUN:
            run += 1
        else:
            pairs.append((current, run))
            current = g
            run = 1
    pairs.append((current, run))

    return b"".join(_PAIR_STRUCT.pack(v, r) for v, r in pairs)


def rle_decode(data: bytes) -> list[int]:
    """
    R4 inverse: Decode RLE-encoded bytes back to gap list.
    Raises ValueError if data length is not a multiple of PAIR_SIZE.
    """
    if not data:
        return []

    if len(data) % PAIR_SIZE != 0:
        raise ValueError(
            f"RLE data length {len(data)} is not a multiple of PAIR_SIZE={PAIR_SIZE}. "
            "Corrupt or truncated stream."
        )

    gaps = []
    offset = 0
    while offset < len(data):
        value, run_length = _PAIR_STRUCT.unpack_from(data, offset)
        offset += PAIR_SIZE
        gaps.extend([value] * run_length)
    return gaps


def rle_size(gaps: list[int]) -> int:
    """Compute the encoded byte size without allocating the full output."""
    if not gaps:
        return 0
    pairs = 1
    current = gaps[0]
    run = 1
    for g in gaps[1:]:
        if g == current and run < MAX_RUN:
            run += 1
        else:
            pairs += 1
            current = g
            run = 1
    return pairs * PAIR_SIZE
