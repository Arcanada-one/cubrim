"""
Canonical Huffman coding over the value-code stream.

Pinned tie-break during tree construction (identical to Rust twin):
  (frequency, monotonic insertion counter, symbol_value for leaves)
  — internal nodes use their own insertion counter; no symbol_value sentinel.

Canonical assignment (DEFLATE-style, identical to Rust twin):
  Sort symbols by (length, symbol_value) ASC → shortest codewords first.
  Increment within a length, left-shift across length boundaries.

Bitstream: MSB-first, byte-aligned, zero-padded final byte.
No task IDs in source; provenance in git log.
"""

import heapq
from typing import Optional


# ─── Huffman tree construction ────────────────────────────────────────────────

class _Node:
    """Priority-queue node for Huffman tree construction."""
    __slots__ = ("freq", "insertion", "symbol", "left", "right")

    def __init__(self, freq: int, insertion: int, symbol: int,
                 left: Optional["_Node"] = None,
                 right: Optional["_Node"] = None):
        self.freq = freq
        self.insertion = insertion
        # For leaves: the symbol code (0..n_distinct).
        # For internal nodes: a large sentinel that sorts last among ties.
        self.symbol = symbol
        self.left = left
        self.right = right

    def __lt__(self, other: "_Node") -> bool:
        # Pinned tie-break: (freq ASC, insertion ASC, symbol ASC)
        return (self.freq, self.insertion, self.symbol) < \
               (other.freq, other.insertion, other.symbol)


def canonical_code_lengths(seq_codes: list[int], n_distinct: int) -> list[int]:
    """
    Compute canonical Huffman code lengths from a sequence of symbol codes.

    seq_codes: list of symbol codes in [0, n_distinct).
    n_distinct: alphabet size.
    Returns list of length n_distinct where code_lengths[s] is the code length
    for symbol s (0 means symbol absent).

    Tie-break (pinned, identical to Rust twin):
      (frequency, monotonic insertion counter, symbol_value for leaves)
    """
    if n_distinct == 0 or not seq_codes:
        return [0] * n_distinct

    # Count frequencies
    freq = [0] * n_distinct
    for c in seq_codes:
        if c < n_distinct:
            freq[c] += 1

    present = [s for s in range(n_distinct) if freq[s] > 0]

    if not present:
        return [0] * n_distinct

    # Single-symbol alphabet: DEFLATE convention — assign length 1
    if len(present) == 1:
        lengths = [0] * n_distinct
        lengths[present[0]] = 1
        return lengths

    # Build min-heap of leaf nodes
    counter = 0
    heap: list[_Node] = []

    for s in present:
        node = _Node(freq=freq[s], insertion=counter, symbol=s)
        counter += 1
        heapq.heappush(heap, node)

    # Huffman tree construction
    while len(heap) > 1:
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        combined_freq = left.freq + right.freq
        # Internal node: symbol = large sentinel (sorts last, does not interfere)
        internal = _Node(freq=combined_freq, insertion=counter,
                         symbol=2**31,  # large sentinel
                         left=left, right=right)
        counter += 1
        heapq.heappush(heap, internal)

    root = heapq.heappop(heap)

    # Extract code lengths via DFS
    lengths = [0] * n_distinct
    _assign_lengths(root, 0, lengths, n_distinct)
    return lengths


def _assign_lengths(node: _Node, depth: int, lengths: list[int], n_distinct: int) -> None:
    if node.left is None and node.right is None:
        # Leaf
        if node.symbol < n_distinct:
            lengths[node.symbol] = depth
        return
    if node.left:
        _assign_lengths(node.left, depth + 1, lengths, n_distinct)
    if node.right:
        _assign_lengths(node.right, depth + 1, lengths, n_distinct)


def assign_canonical_codes(code_len: list[int]) -> list[tuple[int, int]]:
    """
    DEFLATE-style canonical codeword assignment from code lengths.

    code_len: list of length n_distinct. code_len[s]=0 means symbol s is absent.
    Returns list of (codeword: int, length: int) indexed by symbol code.
    Absent symbols get (0, 0) sentinel.

    Canonical assignment:
      Sort symbols by (length, symbol_value) ASC (shortest first, ties by symbol).
      Assign increasing numeric codeword values, left-shift on length increase.
    """
    n = len(code_len)
    result = [(0, 0)] * n

    symbols = sorted([s for s in range(n) if code_len[s] > 0],
                     key=lambda s: (code_len[s], s))
    if not symbols:
        return result

    code = 0
    prev_len = 0

    for sym in symbols:
        length = code_len[sym]
        if prev_len > 0:
            code <<= (length - prev_len)
        result[sym] = (code, length)
        code += 1
        prev_len = length

    return result


def huffman_encode(seq_codes: list[int], code_len: list[int]) -> bytes:
    """
    Huffman-encode seq_codes using the given code lengths.
    Returns MSB-first, byte-aligned, zero-padded bitstream.
    """
    if not seq_codes:
        return b""

    codes = assign_canonical_codes(code_len)
    out = bytearray()
    buf = 0   # bit accumulator
    bits = 0  # bits in buf

    for sym in seq_codes:
        cw, length = codes[sym]
        buf = (buf << length) | cw
        bits += length
        while bits >= 8:
            bits -= 8
            out.append((buf >> bits) & 0xFF)

    # Zero-pad final byte
    if bits > 0:
        out.append((buf << (8 - bits)) & 0xFF)

    return bytes(out)


def huffman_decode(blob: bytes, offset: int, count: int,
                   code_len: list[int]) -> tuple[list[int], int]:
    """
    Huffman-decode count symbols from blob[offset:] using code_len.

    Returns (decoded_symbols, bytes_consumed).
    Raises ValueError on Kraft violation, no-match, truncation, or count mismatch.
    """
    if count == 0:
        return [], 0

    if not kraft_ok(code_len):
        raise ValueError("Huffman decode: Kraft inequality violated (tree not valid)")

    codes = assign_canonical_codes(code_len)

    # Build decode table: (codeword, length) -> symbol
    decode_table: dict[tuple[int, int], int] = {}
    max_len = 0
    for sym, (cw, length) in enumerate(codes):
        if length > 0:
            decode_table[(cw, length)] = sym
            if length > max_len:
                max_len = length

    data = blob[offset:]
    result = []
    bit_pos = 0

    while len(result) < count:
        matched = False
        for length in range(1, max_len + 1):
            end_bit = bit_pos + length
            byte_end = (end_bit + 7) // 8
            if byte_end > len(data):
                raise ValueError(
                    f"Huffman decode: bitstream truncated at bit {bit_pos} "
                    f"(need length {length})"
                )
            cw = _read_bits(data, bit_pos, length)
            if (cw, length) in decode_table:
                result.append(decode_table[(cw, length)])
                bit_pos += length
                matched = True
                break
        if not matched:
            raise ValueError(
                f"Huffman decode: no matching codeword at bit position {bit_pos} "
                "(corrupt stream)"
            )

    if len(result) != count:
        raise ValueError(
            f"Huffman decode: decoded {len(result)} symbols, expected {count}"
        )

    bytes_consumed = (bit_pos + 7) // 8
    return result, bytes_consumed


def huffman_bitstream_size(seq_codes: list[int], code_len: list[int]) -> int:
    """Compute byte size (rounded up) for Huffman encoding seq_codes."""
    total_bits = sum(code_len[s] for s in seq_codes)
    return (total_bits + 7) // 8


def kraft_ok(code_len: list[int]) -> bool:
    """
    Validate Kraft inequality for the given code lengths.

    Returns True iff the lengths form a complete or single-symbol code.
    Single-symbol exception: one symbol with length=1 → Kraft=1/2, still valid.
    """
    present = [l for l in code_len if l > 0]
    if not present:
        return True  # empty alphabet

    # Single-symbol exception (DEFLATE convention)
    if len(present) == 1:
        return present[0] == 1

    max_len = max(present)
    if max_len > 30:
        return False  # pathological depth

    total_capacity = 1 << max_len
    kraft_sum = sum(1 << (max_len - l) for l in present)
    return kraft_sum == total_capacity


def _read_bits(data: bytes, start: int, length: int) -> int:
    """Read length bits from data starting at bit offset start (MSB-first)."""
    val = 0
    for i in range(length):
        bit_idx = start + i
        byte_idx = bit_idx // 8
        bit_shift = 7 - (bit_idx % 8)
        bit = (data[byte_idx] >> bit_shift) & 1
        val = (val << 1) | bit
    return val
