"""
Cubrim prototype — top-level encode/decode orchestration.

# R6: Deterministic decode from header (orchestration layer).
# R7: Mandatory raw-store fallback against blowup.

encode(S: bytes) -> bytes (Cubrim v1 blob):
  1. Domainize (R8): S -> values
  2. Build cube (R1/R2): values -> cube_data
  3. Compute cube encoding size
  4. R7 decision: if cube_size >= len(S) + HEADER_OVERHEAD_BOUND -> mode=1 (raw-store)
  5. mode=0: build distance map (R3/R3.1) -> RLE (R4) -> bitpack values (R5) -> header (R6)
  6. mode=1: header(mode=1, L=len(S)) + S verbatim

decode(blob: bytes) -> bytes:
  1. Parse header (R6) — deterministic, no out-of-band state
  2. mode=1: return raw block directly
  3. mode=0: decode RLE gap streams -> coords -> bitpack values -> cube -> S

HEADER_OVERHEAD_BOUND: small constant (<=256 B) used in R7 comparison.
The exact value is calibrated so the bound holds on all realistic inputs.
"""

import struct

from cubrim_proto.domainize import domainize, de_domainize
from cubrim_proto.cube import build_cube, rebuild_from_cube
from cubrim_proto.distance_map import (
    encode_distance_map,
    decode_distance_map,
    encode_axis_gaps,
    decode_axis_gaps,
)
from cubrim_proto.rle import rle_encode, rle_decode, rle_size, packed_nibble_encode, packed_nibble_decode, packed_nibble_size
from cubrim_proto.bitpack import (
    build_value_dict,
    compute_width,
    bitpack_encode,
    bitpack_decode,
)
from cubrim_proto.header import (
    serialize_header,
    parse_header,
    MODE_CUBE,
    MODE_RAW,
    MAGIC,
    VERSION,
    MAP_SCHEME_RLE,
    MAP_SCHEME_PACKED_NIBBLE,
    VALUE_SCHEME_FIXED,
    VALUE_SCHEME_RLE_CODES,
    VALUE_SCHEME_ENTROPY,
    VALUE_SCHEME_ENTROPY_CONTEXT,
    VALUE_SCHEME_BWT_ENTROPY_CONTEXT,
)
from cubrim_proto.huffman import (
    canonical_code_lengths,
    assign_canonical_codes,
    huffman_encode,
    huffman_decode,
    huffman_bitstream_size,
)

def _compute_min_N(L: int, B: int) -> int:
    """Compute minimum N such that B^N >= L."""
    import math
    if L <= 1:
        return 2
    N = max(2, math.ceil(math.log(L, B)))
    while B ** N < L:
        N += 1
    return N


# R7: header overhead bound constant.
# Maximum header size in cube mode, calibrated for v1-defaults:
# N=2, B=256, n_distinct<=256 bytes (uint8), b_k as uint8, gap_counts as uint16.
# fixed(13) + count(4) + b_k(2) + schemes(3) + n_distinct(2) +
# inverse_dict(256) + traversal_phi(2) + gap_counts(4) = 286 bytes worst case.
# We use 320 as a conservative bound with margin, well under any "blowup" concern.
# For inputs shorter than 320 bytes, raw-store always fires — expected correct behaviour.
# The R7 guarantee: output size <= input_size + HEADER_OVERHEAD_BOUND always holds.
HEADER_OVERHEAD_BOUND: int = 320


def _rle_codes_size(seq_codes: list[int]) -> int:
    """Compute byte size of RLE-codes stream (code:u8 + run:u16 = 3B per triplet)."""
    if not seq_codes:
        return 0
    MAX_RUN = 65535
    triplets = 1
    current = seq_codes[0]
    run = 1
    for c in seq_codes[1:]:
        if c == current and run < MAX_RUN:
            run += 1
        else:
            triplets += 1
            current = c
            run = 1
    return triplets * 3


def _estimate_cube_size(cube_data: dict, dm: dict, value_dict: dict, W: int,
                         gap_scheme: int = MAP_SCHEME_RLE,
                         value_scheme: int = VALUE_SCHEME_FIXED,
                         seq_codes: list[int] | None = None) -> int:
    """
    Estimate the encoded size of the cube representation in bytes.
    Used for R7 mode decision.
    """
    N = cube_data["N"]
    B = cube_data["B"]
    count = cube_data["count"]
    b_k = cube_data["b_k"]
    inverse_dict = sorted(value_dict.keys())  # original values
    n_distinct = len(inverse_dict)

    # Header size
    hdr_size = len(serialize_header(
        mode=MODE_CUBE,
        N=N,
        B=B,
        L=cube_data["L"],
        count=count,
        b_k=b_k,
        map_scheme=gap_scheme,
        W=W,
        inverse_dict=inverse_dict,
        axis_gap_counts=[len(g) for g in dm["axis_gaps"]],
    ))

    # Gap streams size (scheme-dependent)
    if gap_scheme == MAP_SCHEME_PACKED_NIBBLE:
        gap_total = sum(packed_nibble_size(gaps) for gaps in dm["axis_gaps"])
    else:
        gap_total = sum(rle_size(gaps) for gaps in dm["axis_gaps"])

    # Value stream size (value-scheme-dependent)
    if value_scheme == VALUE_SCHEME_RLE_CODES:
        value_total = _rle_codes_size(seq_codes or [])
    elif value_scheme == VALUE_SCHEME_ENTROPY:
        # n_distinct code-length bytes + MSB-first Huffman bitstream
        codes = seq_codes or []
        code_len = canonical_code_lengths(codes, n_distinct)
        value_total = n_distinct + huffman_bitstream_size(codes, code_len)
    elif value_scheme == VALUE_SCHEME_ENTROPY_CONTEXT:
        value_total = _context_huffman_size(seq_codes or [], n_distinct)
    elif value_scheme == VALUE_SCHEME_BWT_ENTROPY_CONTEXT:
        # Wire: varint(primary_index) + EntropyContext payload over BWT-permuted codes.
        codes = seq_codes or []
        if codes:
            bwt_seq, primary_index = _bwt_forward(codes)
            varint_bytes = len(_varint_encode(primary_index))
            ctx_bytes = _context_huffman_size(bwt_seq, n_distinct)
        else:
            varint_bytes = 1  # varint(0) = 1 byte
            ctx_bytes = 2     # empty EntropyContext header (n_contexts=0)
        value_total = varint_bytes + ctx_bytes
    else:
        # Bit-packed values size
        if count > 0:
            value_total = (count * W + 7) // 8
        else:
            value_total = 0

    return hdr_size + gap_total + value_total


def _rle_codes_encode(seq_codes: list[int]) -> bytes:
    """Encode sequential codes as (code:u8, run:u16 BE) triplets."""
    import struct
    MAX_RUN = 65535
    if not seq_codes:
        return b""
    out = []
    current = seq_codes[0]
    run = 1
    for c in seq_codes[1:]:
        if c == current and run < MAX_RUN:
            run += 1
        else:
            out.append(struct.pack(">BH", current, run))
            current = c
            run = 1
    out.append(struct.pack(">BH", current, run))
    return b"".join(out)


# ─── T4 Order-1 Context-Adaptive Huffman ─────────────────────────────────────
#
# Byte-exact mirror of the Rust context_huffman_encode / context_huffman_decode.
# Context = previous value-code (sentinel 0 for position 0).
# Contexts with < MIN_CTX_COUNT observations fall back to the shared order-0
# table stored at ctx_id=0 (FALLBACK_CTX).

_MIN_CTX_COUNT: int = 16
_FALLBACK_CTX: int = 0


# ─── BWT (Burrows-Wheeler Transform) — primary-index variant ─────────────────
#
# Byte-exact mirror of bwt.rs bwt_forward / bwt_inverse / varint_encode / varint_decode.
# Variant (B): primary-index, no sentinel. Alphabet unchanged.


def _bwt_forward(seq_codes: list[int]) -> tuple[list[int], int]:
    """
    Forward BWT. Returns (L, primary_index).
    L[k] = last symbol of k-th lexicographically-sorted rotation.
    primary_index = the index k in the sorted list whose rotation is the identity (offset 0).

    Matches bwt.rs bwt_forward byte-exactly.
    """
    n = len(seq_codes)
    if n == 0:
        return [], 0
    if n == 1:
        return [seq_codes[0]], 0

    # Sort rotation indices. Uses Python's stable sort (timsort), consistent with
    # Rust's stable sort (stable_sort_by). Equal rotations are ordered by original
    # position, which is identical in both implementations (stable insertion order).
    indices = list(range(n))
    indices.sort(key=lambda a: [seq_codes[(a + k) % n] for k in range(n)])

    # primary_index = position of the identity rotation (offset=0) in sorted list
    primary_index = next(k for k, i in enumerate(indices) if i == 0)

    # L[k] = last symbol of k-th sorted rotation = seq_codes[(indices[k] + n - 1) % n]
    l = [seq_codes[(indices[k] + n - 1) % n] for k in range(n)]

    return l, primary_index


def _bwt_inverse(l: list[int], primary_index: int) -> list[int]:
    """
    Inverse BWT using the LF mapping. Reconstructs the original sequence.
    Matches bwt.rs bwt_inverse byte-exactly.
    """
    n = len(l)
    if n == 0:
        return []
    if n == 1:
        return [l[0]]
    if primary_index >= n:
        raise ValueError(f"BWT inverse: primary_index {primary_index} >= n {n}")

    max_sym = max(l)
    n_sym = max_sym + 1

    # Count symbol occurrences in L
    count = [0] * n_sym
    for sym in l:
        count[sym] += 1

    # Starting positions in F (sorted L) for each symbol
    start = [0] * n_sym
    pos = 0
    for c in range(n_sym):
        start[c] = pos
        pos += count[c]

    # Build LF array: lf[k] = start[l[k]] + rank_of_k_among_same_symbol_in_l
    sym_rank = [0] * n_sym
    lf = [0] * n
    for k in range(n):
        sym = l[k]
        lf[k] = start[sym] + sym_rank[sym]
        sym_rank[sym] += 1

    # Walk LF mapping n times from primary_index to recover original in reverse
    result = [0] * n
    k = primary_index
    for i in range(n - 1, -1, -1):
        result[i] = l[k]
        k = lf[k]

    return result


def _varint_encode(value: int) -> bytes:
    """
    Encode value as LEB128 varint. Matches bwt.rs varint_encode.
    """
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(byte)
            break
        else:
            out.append(byte | 0x80)
    return bytes(out)


def _varint_decode(data: bytes, offset: int) -> tuple[int, int]:
    """
    Decode LEB128 varint from data at offset. Returns (value, bytes_consumed).
    Matches bwt.rs varint_decode.
    """
    value = 0
    shift = 0
    consumed = 0
    while True:
        if offset + consumed >= len(data):
            raise ValueError(f"BWT varint: truncated at offset {offset}+{consumed}")
        byte = data[offset + consumed]
        consumed += 1
        low7 = byte & 0x7F
        value |= low7 << shift
        shift += 7
        if byte & 0x80 == 0:
            break
        if shift >= 64:
            raise ValueError("BWT varint: overflow (more than 9 bytes)")
    return value, consumed


def _build_context_tables(seq_codes: list[int], n_distinct: int) -> list[tuple[int, list[int]]]:
    """
    Build per-context canonical Huffman code-length tables.
    Returns list of (ctx_id, code_len) sorted ascending by ctx_id.
    ctx_id=0 is always the fallback (order-0) table.
    """
    if not seq_codes or n_distinct == 0:
        return []

    # Count per-context occurrences and global (fallback) counts.
    from collections import defaultdict
    ctx_freq: dict[int, list[int]] = defaultdict(lambda: [0] * n_distinct)
    fallback_freq: list[int] = [0] * n_distinct

    prev_ctx: int = 0  # sentinel for position 0
    for code in seq_codes:
        ctx_freq[prev_ctx][code] += 1
        fallback_freq[code] += 1
        prev_ctx = code

    # Build fallback code_len (global order-0).
    fallback_seq: list[int] = []
    for sym, cnt in enumerate(fallback_freq):
        fallback_seq.extend([sym] * cnt)
    fallback_code_len = canonical_code_lengths(fallback_seq, n_distinct)

    result: list[tuple[int, list[int]]] = [(_FALLBACK_CTX, fallback_code_len)]

    # Add per-context tables for contexts meeting MIN_CTX_COUNT.
    for ctx, freq in sorted(ctx_freq.items()):
        obs = sum(freq)
        if obs < _MIN_CTX_COUNT:
            continue
        ctx_seq: list[int] = []
        for sym, cnt in enumerate(freq):
            ctx_seq.extend([sym] * cnt)
        ctx_len = canonical_code_lengths(ctx_seq, n_distinct)
        result.append((ctx, ctx_len))

    # Sort ascending by ctx_id (fallback=0 first).
    result.sort(key=lambda x: x[0])
    return result


def _context_huffman_size(seq_codes: list[int], n_distinct: int) -> int:
    """Estimate byte size of T4 encoded stream without full allocation."""
    if not seq_codes:
        return 2  # n_contexts=0 header
    ctx_tables = _build_context_tables(seq_codes, n_distinct)
    n_ctx = len(ctx_tables)
    header_bytes = 2 + n_ctx * (2 + n_distinct)

    # Build index for lookup.
    ctx_idx: dict[int, int] = {ctx_id: i for i, (ctx_id, _) in enumerate(ctx_tables)}
    fallback_idx = ctx_idx.get(_FALLBACK_CTX, 0)
    canonical: list[list[tuple[int, int]]] = [
        assign_canonical_codes(code_len) for _, code_len in ctx_tables
    ]

    total_bits = 0
    prev_ctx = 0
    for code in seq_codes:
        tbl_idx = ctx_idx.get(prev_ctx, fallback_idx)
        _, length = canonical[tbl_idx][code]
        total_bits += length
        prev_ctx = code

    return header_bytes + (total_bits + 7) // 8


def _context_huffman_encode(seq_codes: list[int], n_distinct: int) -> bytes:
    """Encode value-code stream with order-1 context-adaptive canonical Huffman."""
    if not seq_codes:
        return b"\x00\x00"  # n_contexts=0

    ctx_tables = _build_context_tables(seq_codes, n_distinct)
    n_ctx = len(ctx_tables)

    ctx_idx: dict[int, int] = {ctx_id: i for i, (ctx_id, _) in enumerate(ctx_tables)}
    fallback_idx = ctx_idx.get(_FALLBACK_CTX, 0)
    canonical: list[list[tuple[int, int]]] = [
        assign_canonical_codes(code_len) for _, code_len in ctx_tables
    ]

    # Encode bitstream.
    bit_acc: int = 0
    bit_count: int = 0
    bitstream: bytearray = bytearray()

    prev_ctx: int = 0
    for code in seq_codes:
        tbl_idx = ctx_idx.get(prev_ctx, fallback_idx)
        codeword, length = canonical[tbl_idx][code]
        bit_acc = (bit_acc << length) | codeword
        bit_count += length
        while bit_count >= 8:
            bit_count -= 8
            bitstream.append((bit_acc >> bit_count) & 0xFF)
        prev_ctx = code

    if bit_count > 0:
        bitstream.append((bit_acc << (8 - bit_count)) & 0xFF)

    # Serialize header.
    import struct
    out = bytearray()
    out += struct.pack(">H", n_ctx)
    for ctx_id, code_len in ctx_tables:
        out += struct.pack(">H", ctx_id)
        out += bytes(code_len)
    out += bitstream
    return bytes(out)


def _context_huffman_decode(blob: bytes, offset: int, count: int, n_distinct: int) -> tuple[list[int], int]:
    """Decode order-1 context-adaptive Huffman from blob at offset."""
    import struct

    if count == 0:
        if offset + 2 > len(blob):
            raise ValueError("EntropyContext: blob too short for n_contexts")
        n_ctx = struct.unpack_from(">H", blob, offset)[0]
        header_bytes = 2 + n_ctx * (2 + n_distinct)
        return [], header_bytes

    if offset + 2 > len(blob):
        raise ValueError("EntropyContext: blob too short for n_contexts")

    n_ctx = struct.unpack_from(">H", blob, offset)[0]
    pos = offset + 2

    header_entry_size = 2 + n_distinct
    if pos + n_ctx * header_entry_size > len(blob):
        raise ValueError(
            f"EntropyContext: context table header truncated: "
            f"need {n_ctx * header_entry_size} bytes"
        )

    # Read context tables and build decode maps: (codeword, length) -> symbol.
    ctx_tables: list[tuple[int, dict[tuple[int, int], int]]] = []
    for _ in range(n_ctx):
        ctx_id = struct.unpack_from(">H", blob, pos)[0]
        pos += 2
        code_len = list(blob[pos:pos + n_distinct])
        pos += n_distinct
        canonical = assign_canonical_codes(code_len)
        decode_table: dict[tuple[int, int], int] = {}
        for sym, (codeword, length) in enumerate(canonical):
            if length > 0:
                decode_table[(codeword, length)] = sym
        ctx_tables.append((ctx_id, decode_table))

    ctx_idx: dict[int, int] = {ctx_id: i for i, (ctx_id, _) in enumerate(ctx_tables)}
    fallback_idx = ctx_idx.get(_FALLBACK_CTX, 0)

    # Decode bitstream.
    bitstream_offset = pos
    bit_pos = 0  # bit position from bitstream_offset
    decoded: list[int] = []
    prev_ctx: int = 0

    for sym_num in range(count):
        tbl_idx = ctx_idx.get(prev_ctx, fallback_idx)
        decode_table = ctx_tables[tbl_idx][1]

        codeword = 0
        found = False
        for length in range(1, 33):
            byte_off = bitstream_offset + bit_pos // 8
            bit_off = 7 - (bit_pos % 8)
            if byte_off >= len(blob):
                raise ValueError(
                    f"EntropyContext: bitstream exhausted at bit {bit_pos} "
                    f"decoding symbol {sym_num}/{count}"
                )
            bit = (blob[byte_off] >> bit_off) & 1
            codeword = (codeword << 1) | bit
            bit_pos += 1
            if (codeword, length) in decode_table:
                sym = decode_table[(codeword, length)]
                decoded.append(sym)
                prev_ctx = sym
                found = True
                break
        if not found:
            raise ValueError(
                f"EntropyContext: no codeword match after 32 bits at symbol {sym_num}/{count}"
            )

    bitstream_bytes = (bit_pos + 7) // 8
    total_consumed = (pos - offset) + bitstream_bytes
    return decoded, total_consumed


def encode(data: bytes, gap_scheme: int = MAP_SCHEME_RLE, n_override: int | None = None,
           value_scheme: int = VALUE_SCHEME_FIXED) -> bytes:
    """
    R6/R7: Encode input bytes to Cubrim v1 format.

    Returns a blob that:
    - If mode=1 (raw-store): header + data verbatim; size <= len(data) + HEADER_OVERHEAD_BOUND
    - If mode=0 (cube): header + gap streams + bitpacked values

    gap_scheme: MAP_SCHEME_RLE (default, v1-compatible) or MAP_SCHEME_PACKED_NIBBLE.
    n_override: force N dimensions; clamped up to N_min if smaller.
    value_scheme: VALUE_SCHEME_FIXED (default, v1-compatible) or VALUE_SCHEME_RLE_CODES.
    """
    L = len(data)
    B = 256  # v1-default

    # Special case: empty input -> raw-store (trivial)
    if L == 0:
        hdr = serialize_header(mode=MODE_RAW, N=2, B=B, L=0)
        return hdr

    # R7 fast-path: if L >= HEADER_OVERHEAD_BOUND, compute minimum N needed.
    N_min = _compute_min_N(L, B)
    # Apply N override; clamp to N_min for injectivity
    N_use = max(N_min, n_override) if n_override is not None else N_min

    if L > B ** 2:
        hdr = serialize_header(mode=MODE_RAW, N=N_use, B=B, L=L)
        return hdr + data

    if L <= HEADER_OVERHEAD_BOUND:
        hdr = serialize_header(mode=MODE_RAW, N=N_use, B=B, L=L)
        return hdr + data

    # Step 1: R8 domainize
    values = domainize(data)

    # Step 2: R1/R2 build cube (with N override)
    cube_data = build_cube(data, B=B, N=N_use)
    N = cube_data["N"]
    B = cube_data["B"]
    b_k = cube_data["b_k"]
    populated = cube_data["populated"]

    # Step 3: R5 shift-to-corner — build value dictionary
    value_dict = build_value_dict(values)
    n_distinct = len(value_dict)
    W = compute_width(n_distinct)
    inverse_dict_list = sorted(value_dict.keys())

    # Step 4: R3/R3.1 build distance map
    dm = encode_distance_map(cube_data)

    # Build sequential (i-order) codes for RleCodes estimation / encoding.
    # populated is lex-sorted; build i->code by inverting phi for each populated point.
    from cubrim_proto.phi import phi_inv as phi_inv_fn
    idx_to_code = [0] * L
    for coords, val in populated:
        i = phi_inv_fn(coords, B=B)
        if i < L:
            idx_to_code[i] = value_dict[val]
    seq_codes = idx_to_code  # codes in sequential (i) order

    # Step 5: R7 decision
    cube_size = _estimate_cube_size(cube_data, dm, value_dict, W,
                                    gap_scheme=gap_scheme,
                                    value_scheme=value_scheme,
                                    seq_codes=seq_codes)
    raw_header_bytes = serialize_header(mode=MODE_RAW, N=N, B=B, L=L)
    raw_output_size = len(raw_header_bytes) + L

    if cube_size >= raw_output_size:
        return raw_header_bytes + data

    # Step 6: Encode gap streams (scheme-dispatched)
    if gap_scheme == MAP_SCHEME_PACKED_NIBBLE:
        gap_streams = [packed_nibble_encode(gaps) for gaps in dm["axis_gaps"]]
    else:
        gap_streams = [rle_encode(gaps) for gaps in dm["axis_gaps"]]
    axis_gap_counts = [len(dm["axis_gaps"][k]) for k in range(N)]

    # Step 7: Encode value stream (value-scheme-dispatched)
    if value_scheme == VALUE_SCHEME_RLE_CODES:
        encoded_values = _rle_codes_encode(seq_codes)
    elif value_scheme == VALUE_SCHEME_ENTROPY:
        # Canonical Huffman on codes in sequential i-order.
        # Wire: [code_len[0..n_distinct]: u8 × n_distinct] + [MSB-first bitstream]
        n_distinct_enc = len(inverse_dict_list)
        code_len = canonical_code_lengths(seq_codes, n_distinct_enc)
        encoded_values = bytes(code_len) + huffman_encode(seq_codes, code_len)
    elif value_scheme == VALUE_SCHEME_ENTROPY_CONTEXT:
        # Order-1 context-adaptive canonical Huffman (T4).
        encoded_values = _context_huffman_encode(seq_codes, len(inverse_dict_list))
    elif value_scheme == VALUE_SCHEME_BWT_ENTROPY_CONTEXT:
        # BWT pre-pass + order-1 context-adaptive canonical Huffman (T5).
        # Wire: [primary_index : LEB128 varint] [EntropyContext payload over BWT codes]
        bwt_seq, primary_index = _bwt_forward(seq_codes)
        encoded_values = _varint_encode(primary_index) + _context_huffman_encode(bwt_seq, len(inverse_dict_list))
    else:
        # BitpackFixed: lex-order point values, W bits each (v1-default)
        point_values = [p[1] for p in populated]
        encoded_values = bitpack_encode(point_values, value_dict, W)

    # Step 8: R6 serialize header (with gap_scheme and value_scheme bytes)
    hdr = serialize_header(
        mode=MODE_CUBE,
        N=N,
        B=B,
        L=L,
        count=len(populated),
        b_k=b_k,
        map_scheme=gap_scheme,
        W=W,
        inverse_dict=inverse_dict_list,
        axis_gap_counts=axis_gap_counts,
        value_scheme=value_scheme,
    )

    return hdr + b"".join(gap_streams) + encoded_values


def decode(blob: bytes) -> bytes:
    """
    R6: Decode a Cubrim v1 blob back to original bytes.

    Deterministic decode from header alone — no out-of-band state.
    Corrupt input raises ValueError or struct.error (never silent garbage).
    """
    # Parse header (R6) — raises on bad magic/version/truncation
    hdr, offset = parse_header(blob)

    L = hdr["L"]

    # R7: raw-store mode — return payload directly
    if hdr["mode"] == MODE_RAW:
        payload = blob[offset:]
        if len(payload) < L:
            raise ValueError(
                f"Raw-store payload too short: got {len(payload)} bytes, "
                f"expected {L} bytes (from header L field)."
            )
        return payload[:L]

    # mode == MODE_CUBE
    if hdr["mode"] != MODE_CUBE:
        raise ValueError(f"Unknown mode in header: {hdr['mode']}")

    # Empty input special case
    if L == 0:
        return b""

    N = hdr["N"]
    B = hdr["B"]
    b_k = hdr["b_k"]
    count = hdr["count"]
    W = hdr["W"]
    inverse_dict = hdr["inverse_dict"]
    axis_gap_counts = hdr["axis_gap_counts"]

    # Validate basic consistency
    if len(b_k) != N:
        raise ValueError(f"b_k length {len(b_k)} != N={N}")
    if len(axis_gap_counts) != N:
        raise ValueError(f"axis_gap_counts length != N={N}")

    # Determine gap scheme from header
    map_scheme = hdr.get("map_scheme", MAP_SCHEME_RLE)
    if map_scheme not in (MAP_SCHEME_RLE, MAP_SCHEME_PACKED_NIBBLE):
        raise ValueError(f"Unknown map_scheme={map_scheme} in header")

    # Determine value scheme from header
    value_scheme = hdr.get("value_scheme", VALUE_SCHEME_FIXED)
    if value_scheme not in (VALUE_SCHEME_FIXED, VALUE_SCHEME_RLE_CODES,
                            VALUE_SCHEME_ENTROPY, VALUE_SCHEME_ENTROPY_CONTEXT,
                            VALUE_SCHEME_BWT_ENTROPY_CONTEXT):
        raise ValueError(f"Unknown value_scheme={value_scheme} in header")

    # Read and decode gap streams for each axis (scheme-dispatched)
    axis_coords = []
    for k in range(N):
        n_gaps = axis_gap_counts[k]

        if map_scheme == MAP_SCHEME_PACKED_NIBBLE:
            gaps_k, consumed = packed_nibble_decode(blob, offset, n_gaps)
            offset += consumed
        else:
            stream_bytes = _read_rle_stream(blob, offset, n_gaps)
            gaps_k = rle_decode(stream_bytes)
            offset += len(stream_bytes)

        if len(gaps_k) != n_gaps:
            raise ValueError(
                f"Axis {k}: decoded {len(gaps_k)} gaps, expected {n_gaps}"
            )
        # Validate gap invariant on decode
        for i, g in enumerate(gaps_k):
            if g < 1:
                raise ValueError(
                    f"Axis {k} gap[{i}]={g} < 1 — corrupt stream (gap invariant violated)"
                )
            if g > b_k[k]:
                raise ValueError(
                    f"Axis {k} gap[{i}]={g} > b_k[{k}]={b_k[k]} — corrupt stream"
                )
        coords_k = decode_axis_gaps(gaps_k)
        axis_coords.append(coords_k)

    if value_scheme == VALUE_SCHEME_BWT_ENTROPY_CONTEXT:
        # BWT inverse + order-1 context-adaptive Huffman decode (T5).
        # Wire: [primary_index : LEB128 varint] [EntropyContext payload over BWT codes]
        n_distinct = hdr["n_distinct"]

        # Step 1: read primary_index varint
        primary_index, varint_consumed = _varint_decode(blob, offset)
        ctx_offset = offset + varint_consumed

        # Step 2: decode the BWT-permuted code sequence using EntropyContext
        bwt_codes, _consumed = _context_huffman_decode(blob, ctx_offset, count, n_distinct)

        if len(bwt_codes) != count:
            raise ValueError(
                f"BwtEntropyContext: EntropyContext decoded {len(bwt_codes)} codes "
                f"but expected {count} (count from header)"
            )

        # Step 3: apply BWT inverse to restore i-order seq_codes
        seq_codes_dec = _bwt_inverse(bwt_codes, primary_index)

        if len(seq_codes_dec) != count:
            raise ValueError(
                f"BwtEntropyContext: BWT inverse produced {len(seq_codes_dec)} codes "
                f"but expected {count}"
            )

        # Step 4: reconstruct original byte sequence
        result = bytearray(L)
        for i, code in enumerate(seq_codes_dec):
            if code >= n_distinct:
                raise ValueError(
                    f"BwtEntropyContext: code {code} at position {i} >= n_distinct "
                    f"{n_distinct} after BWT inverse"
                )
            if i < L:
                result[i] = inverse_dict[code]

        return bytes(result)

    if value_scheme == VALUE_SCHEME_ENTROPY_CONTEXT:
        # Order-1 context-adaptive Huffman decode (T4).
        n_distinct = hdr["n_distinct"]
        seq_codes_dec, _consumed = _context_huffman_decode(blob, offset, count, n_distinct)

        if len(seq_codes_dec) != count:
            raise ValueError(
                f"EntropyContext decoded {len(seq_codes_dec)} codes but expected {count}"
            )

        result = bytearray(L)
        for i, code in enumerate(seq_codes_dec):
            if code >= n_distinct:
                raise ValueError(
                    f"EntropyContext code {code} at position {i} >= n_distinct {n_distinct}"
                )
            if i < L:
                result[i] = inverse_dict[code]

        return bytes(result)

    if value_scheme == VALUE_SCHEME_ENTROPY:
        # Entropy decode: read n_distinct code-length bytes, then Huffman bitstream.
        n_distinct = hdr["n_distinct"]
        if offset + n_distinct > len(blob):
            raise ValueError(
                f"Entropy: code-length table truncated: need {n_distinct} bytes at "
                f"offset {offset}, have {len(blob)} total"
            )
        code_len = list(blob[offset:offset + n_distinct])
        huff_offset = offset + n_distinct

        seq_codes_dec, _consumed = huffman_decode(blob, huff_offset, count, code_len)

        if len(seq_codes_dec) != count:
            raise ValueError(
                f"Entropy decoded {len(seq_codes_dec)} codes but expected {count}"
            )

        result = bytearray(L)
        for i, code in enumerate(seq_codes_dec):
            if code >= n_distinct:
                raise ValueError(
                    f"Entropy code {code} at position {i} >= n_distinct {n_distinct}"
                )
            if i < L:
                result[i] = inverse_dict[code]

        return bytes(result)

    if value_scheme == VALUE_SCHEME_RLE_CODES:
        # RleCodes path: value codes are stored in sequential (i-order) input order.
        # Each RLE triplet: (code: u8, run_length: u16 BE) = 3 bytes.
        # Decode: expand triplets -> seq_codes[i] for i in [0, count).
        # Reconstruct: result[i] = inverse_dict[seq_codes[i]] directly (no lex rebuild).
        import struct
        seq_codes = []
        pos = offset
        while len(seq_codes) < count:
            if pos + 3 > len(blob):
                raise ValueError(
                    f"RleCodes stream truncated at offset {pos}: need code+run (3B), "
                    f"have {len(blob) - pos}B remaining"
                )
            code, run = struct.unpack_from(">BH", blob, pos)
            pos += 3
            if run == 0:
                raise ValueError(
                    f"RleCodes run_length=0 at offset {pos - 3}: invalid (stream corrupt)"
                )
            remaining = count - len(seq_codes)
            if run > remaining:
                raise ValueError(
                    f"RleCodes run {run} would exceed remaining count {remaining}: "
                    "corrupt stream"
                )
            seq_codes.extend([code] * run)

        if len(seq_codes) != count:
            raise ValueError(
                f"RleCodes decoded {len(seq_codes)} codes but expected {count}"
            )

        result = bytearray(L)
        for i, code in enumerate(seq_codes):
            if code >= len(inverse_dict):
                raise ValueError(
                    f"RleCodes code {code} at position {i} >= n_distinct {len(inverse_dict)}"
                )
            if i < L:
                result[i] = inverse_dict[code]

        return bytes(result)

    # VALUE_SCHEME_FIXED path (default):
    # Bitpacked values are in lex-sorted point order (W bits each).

    # Read bitpacked values
    bitpack_bytes_count = (count * W + 7) // 8 if count > 0 else 0
    packed_values_bytes = blob[offset:offset + bitpack_bytes_count]
    offset += bitpack_bytes_count

    # Decode bitpacked values
    values = bitpack_decode(packed_values_bytes, W, count, inverse_dict)

    # Reconstruct sparse cube:
    # During encode, cube.py builds (phi(i), value[i]) for each i in [0, L-1],
    # then sorts by phi(i) coordinates in lexicographic order.
    # Values are stored in that lex-sorted order.
    #
    # NOTE: lex order of phi(i) coords != sequential index order for N=2, B=256.
    # Example: phi(256)=(0,1) < phi(1)=(1,0) in lex order.
    # Therefore we must:
    #   1. Reconstruct the lex-sorted list of phi(i) for i in [0, L-1]
    #   2. For the j-th entry in lex order, result[phi_inv(coords)] = values[j]
    #
    # This is deterministic from (L, N, B) alone — no out-of-band state needed (R6).

    from cubrim_proto.phi import phi as phi_fn, phi_inv as phi_inv_fn

    # Rebuild the lex-sorted coordinate sequence (same order as cube.py used)
    lex_sorted_coords = sorted(
        [phi_fn(i, N=N, B=B) for i in range(L)]
    )

    result = bytearray(L)
    for j, coords in enumerate(lex_sorted_coords):
        orig_idx = phi_inv_fn(coords, B=B)
        if orig_idx < L and j < len(values):
            result[orig_idx] = values[j]

    return bytes(result)


def _read_rle_stream(blob: bytes, offset: int, n_gaps: int) -> bytes:
    """
    Read enough RLE pairs from blob starting at offset to decode n_gaps gaps.
    Each RLE pair is 4 bytes. We need to read pairs until total run_lengths sum to n_gaps.
    Returns the bytes consumed.
    """
    import struct
    _PAIR = struct.Struct(">HH")
    PAIR_SIZE = 4

    if n_gaps == 0:
        return b""

    total_decoded = 0
    bytes_read = 0
    pos = offset

    while total_decoded < n_gaps:
        if pos + PAIR_SIZE > len(blob):
            raise ValueError(
                f"RLE stream truncated: need more pairs to decode {n_gaps} gaps, "
                f"got {total_decoded} so far."
            )
        _value, run_length = _PAIR.unpack_from(blob, pos)
        total_decoded += run_length
        pos += PAIR_SIZE
        bytes_read += PAIR_SIZE

    if total_decoded != n_gaps:
        raise ValueError(
            f"RLE stream over-reads: decoded {total_decoded} gaps, expected {n_gaps}."
        )

    return blob[offset:offset + bytes_read]
