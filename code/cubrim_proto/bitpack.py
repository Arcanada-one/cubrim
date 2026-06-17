"""
Cubrim prototype — shift-to-corner + fixed-width bit-packing of values.

# R5: Shift-to-corner dense re-indexing + explicit fixed-width bit-packing.

'Shift to corner' = map the populated values to a dense local code starting at 0.
The mapping (value_dict) is stored in the header (R6) so the decoder can invert it.

Explicit fixed width W = ceil(log2(max_local_code + 1)) stored in header.
Context-derived width is FORBIDDEN in v1 (R5 hard rule against silent round-trip breakage).
No-delimiter: values are packed back-to-back at W bits each; width comes from header only.

Resolution criterion (OQ-4): a scheme minimising bits-per-value on the corpus beats
this baseline (challengers: per-sub-cube width, Elias/Golomb codes, context-adaptive).
"""

import math
import struct


def build_value_dict(values: list[int]) -> dict[int, int]:
    """
    R5: Shift-to-corner: build a dense mapping from distinct values to [0, n-1].
    Returns dict: original_value -> dense_code.
    The inverse (dense_code -> original_value) is stored in the header.
    """
    distinct = sorted(set(values))
    return {v: i for i, v in enumerate(distinct)}


def compute_width(n_distinct: int) -> int:
    """
    R5: Fixed width W = ceil(log2(n_distinct)) bits.
    Minimum 1 bit (for n_distinct <= 1).
    """
    if n_distinct <= 1:
        return 1
    return math.ceil(math.log2(n_distinct))


def bitpack_encode(values: list[int], value_dict: dict[int, int], W: int) -> bytes:
    """
    R5: Encode list of values using shift-to-corner + fixed W-bit packing.
    No delimiters — decoder uses W from header.

    Returns packed bytes. Final byte is zero-padded if needed.
    """
    if not values:
        return b""

    # Build bit string
    bits = 0
    bit_count = 0
    for v in values:
        code = value_dict[v]
        bits = (bits << W) | (code & ((1 << W) - 1))
        bit_count += W

    # Convert to bytes (big-endian, zero-padded)
    total_bytes = (bit_count + 7) // 8
    padding = total_bytes * 8 - bit_count
    bits <<= padding  # pad to byte boundary

    result = bytearray(total_bytes)
    for i in range(total_bytes - 1, -1, -1):
        result[i] = bits & 0xFF
        bits >>= 8
    return bytes(result)


def bitpack_decode(data: bytes, W: int, count: int,
                   inverse_dict: list[int]) -> list[int]:
    """
    R5 inverse: Decode W-bit packed values from bytes.

    Args:
      data: packed bytes from bitpack_encode
      W: fixed bit width (from header — NEVER derived from context)
      count: number of values to decode (from header)
      inverse_dict: list where inverse_dict[code] = original_value

    Returns list of original values.
    """
    if count == 0:
        return []
    if not data:
        raise ValueError("Empty data but count > 0 in bitpack_decode")

    # Convert bytes to integer
    bits = 0
    for byte in data:
        bits = (bits << 8) | byte

    # Total bits used (with padding at the end)
    total_bits = len(data) * 8
    padding = total_bits - count * W
    if padding < 0:
        raise ValueError(
            f"Insufficient data: {len(data)} bytes = {total_bits} bits, "
            f"need {count * W} bits for {count} values at W={W}"
        )

    # Remove padding bits (they're at the least significant end)
    bits >>= padding

    # Extract W-bit codes in reverse (most significant first)
    mask = (1 << W) - 1
    codes = []
    for _ in range(count):
        codes.append(bits & mask)
        bits >>= W

    # Codes were extracted in reverse order
    codes.reverse()

    # Map codes back to original values
    max_code = len(inverse_dict) - 1
    result = []
    for code in codes:
        if code > max_code:
            raise ValueError(
                f"Decoded code {code} exceeds inverse_dict size {len(inverse_dict)}. "
                "Corrupt stream or wrong W."
            )
        result.append(inverse_dict[code])
    return result
