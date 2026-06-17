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
from cubrim_proto.rle import rle_encode, rle_decode, rle_size
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


def _estimate_cube_size(cube_data: dict, dm: dict, value_dict: dict, W: int) -> int:
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
        W=W,
        inverse_dict=inverse_dict,
        axis_gap_counts=[len(g) for g in dm["axis_gaps"]],
    ))

    # RLE-encoded gap streams size
    rle_total = sum(rle_size(gaps) for gaps in dm["axis_gaps"])

    # Bit-packed values size
    if count > 0:
        bitpack_total = (count * W + 7) // 8
    else:
        bitpack_total = 0

    return hdr_size + rle_total + bitpack_total


def encode(data: bytes) -> bytes:
    """
    R6/R7: Encode input bytes to Cubrim v1 format.

    Returns a blob that:
    - If mode=1 (raw-store): header + data verbatim; size <= len(data) + HEADER_OVERHEAD_BOUND
    - If mode=0 (cube): header + RLE gap streams + bitpacked values
    """
    L = len(data)
    B = 256  # v1-default

    # Special case: empty input -> raw-store (trivial)
    if L == 0:
        hdr = serialize_header(mode=MODE_RAW, N=2, B=B, L=0)
        return hdr

    # R7 fast-path: if L >= HEADER_OVERHEAD_BOUND, compute minimum N needed.
    # At density=1 (all positions populated), the cube mode cannot compress —
    # the gap stream has all gaps=1, RLE gives 1 pair per axis = tiny savings,
    # but bitpacked values need L*W bits which is always >= L bytes for W>=8.
    # For L > B^2 = 65536 (with B=256, N=2), cube mode ALWAYS expands:
    # value stream alone = L * ceil(log2(256)) / 8 = L bytes (W=8 for 256 distinct values).
    # Plus gap overhead + header. Skip cube build entirely, go straight to raw-store.
    N_min = _compute_min_N(L, B)
    if L > B ** 2:
        # Cannot compress: L > 65536 requires N>2; density >= 1 at N=2.
        # At N>2 the cube is larger; raw-store is always better.
        hdr = serialize_header(mode=MODE_RAW, N=N_min, B=B, L=L)
        return hdr + data

    # For small inputs that will always raw-store, skip the cube build too
    # (size(values_bitpacked) >= L since W >= 1 and we have all L values)
    if L <= HEADER_OVERHEAD_BOUND:
        # Output would be at least L bytes of values; plus header >= HEADER_OVERHEAD_BOUND
        # So cube mode always >= L + HEADER_OVERHEAD_BOUND → raw-store wins.
        hdr = serialize_header(mode=MODE_RAW, N=N_min, B=B, L=L)
        return hdr + data

    # Step 1: R8 domainize
    values = domainize(data)

    # Step 2: R1/R2 build cube
    cube_data = build_cube(data)
    N = cube_data["N"]
    B = cube_data["B"]
    b_k = cube_data["b_k"]
    populated = cube_data["populated"]

    # Step 3: R5 shift-to-corner — build value dictionary
    value_dict = build_value_dict(values)
    n_distinct = len(value_dict)
    W = compute_width(n_distinct)
    # inverse_dict: list where index = dense code, value = original value
    inverse_dict_list = sorted(value_dict.keys())  # original values in code order

    # Step 4: R3/R3.1 build distance map
    dm = encode_distance_map(cube_data)

    # Step 5: R7 decision — compare cube encoded size vs raw-store output size.
    # raw-store output = raw_header (fixed ~13B) + L bytes
    # cube mode wins only if cube_size < raw_output_size (strictly smaller).
    # R7 rule: "if size(cube) >= size(raw_input) + header_overhead → raw-store"
    # where header_overhead is the raw-mode header size (not cube header).
    cube_size = _estimate_cube_size(cube_data, dm, value_dict, W)
    raw_header_bytes = serialize_header(mode=MODE_RAW, N=N, B=B, L=L)
    raw_output_size = len(raw_header_bytes) + L

    if cube_size >= raw_output_size:
        # R7: cube does not improve on raw; use raw-store
        return raw_header_bytes + data

    # Step 6: R4 RLE-encode gap streams
    rle_streams = [rle_encode(gaps) for gaps in dm["axis_gaps"]]
    axis_gap_counts = [len(dm["axis_gaps"][k]) for k in range(N)]

    # Step 7: R5 bitpack values (in lex-sorted point order)
    point_values = [p[1] for p in populated]
    packed_values = bitpack_encode(point_values, value_dict, W)

    # Step 8: R6 serialize header
    hdr = serialize_header(
        mode=MODE_CUBE,
        N=N,
        B=B,
        L=L,
        count=len(populated),
        b_k=b_k,
        W=W,
        inverse_dict=inverse_dict_list,
        axis_gap_counts=axis_gap_counts,
    )

    return hdr + b"".join(rle_streams) + packed_values


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

    # Read RLE streams for each axis
    rle_streams = []
    for k in range(N):
        n_gaps = axis_gap_counts[k]
        # Each gap pair is 4 bytes (value u16 + run_length u16)
        # But we need to read until we have enough gaps — we know n_gaps
        # Read pairs until decoded gap count reaches n_gaps
        stream_bytes = _read_rle_stream(blob, offset, n_gaps)
        rle_streams.append(stream_bytes)
        # Advance offset by actual bytes consumed
        offset += len(stream_bytes)

    # Read bitpacked values
    bitpack_bytes_count = (count * W + 7) // 8 if count > 0 else 0
    packed_values_bytes = blob[offset:offset + bitpack_bytes_count]
    offset += bitpack_bytes_count

    # Decode RLE gap streams -> axis coordinates
    axis_coords = []
    for k in range(N):
        gaps_k = rle_decode(rle_streams[k])
        if len(gaps_k) != axis_gap_counts[k]:
            raise ValueError(
                f"Axis {k}: decoded {len(gaps_k)} gaps, expected {axis_gap_counts[k]}"
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
