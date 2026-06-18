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
    if value_scheme not in (VALUE_SCHEME_FIXED, VALUE_SCHEME_RLE_CODES):
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
