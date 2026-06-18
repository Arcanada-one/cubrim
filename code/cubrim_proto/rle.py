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


# ----- PackedNibble (varint-per-gap) encoding -----
#
# Each gap encoded as LEB128-style unsigned varint (little-endian 7-bit groups).
# 1 byte for g in [1,127], 2 bytes for [128,16383], etc.
# Mirrors Rust rle.rs packed_nibble_encode / packed_nibble_decode.

def packed_nibble_encode(gaps: list[int]) -> bytes:
    """Encode gaps as varint-per-gap (PackedNibble scheme)."""
    out = bytearray()
    for g in gaps:
        while True:
            b = g & 0x7F
            g >>= 7
            if g == 0:
                out.append(b)      # last byte: high bit = 0
                break
            else:
                out.append(b | 0x80)  # more bytes follow: high bit = 1
    return bytes(out)


def packed_nibble_decode(data: bytes, offset: int, n_gaps: int) -> tuple[list[int], int]:
    """
    Decode exactly n_gaps varints from data starting at offset.
    Returns (gaps, bytes_consumed).
    """
    gaps = []
    pos = offset
    for _ in range(n_gaps):
        value = 0
        shift = 0
        while True:
            if pos >= len(data):
                raise ValueError(f"PackedNibble varint truncated at offset {pos}")
            byte = data[pos]
            pos += 1
            value |= (byte & 0x7F) << shift
            shift += 7
            if byte & 0x80 == 0:
                break
            if shift >= 64:
                raise ValueError("PackedNibble varint overflow")
        gaps.append(value)
    return gaps, pos - offset


def packed_nibble_size(gaps: list[int]) -> int:
    """Compute encoded byte size for PackedNibble without allocating."""
    total = 0
    for g in gaps:
        if g < 0x80:
            total += 1
        elif g < 0x4000:
            total += 2
        elif g < 0x200000:
            total += 3
        else:
            total += 4
    return total
