"""
Cubrim prototype — file header serialization and parsing.

# R6: Self-describing header for deterministic decode without out-of-band state.

Header layout (binary, big-endian):
  [magic 4B][version 1B][mode 1B][N 1B][B 2B][L 4B]
  [count 4B (mode 0 only)]
  [b_k N*2B (mode 0 only)]
  [map_scheme 1B (mode 0 only)]
  [value_scheme 1B (mode 0 only)]
  [W 1B (mode 0 only)]
  [n_distinct 2B (mode 0 only)]
  [inverse_dict n_distinct*2B (mode 0 only)]
  [traversal 1B (mode 0 only)]
  [phi_id 1B (mode 0 only)]
  [n_axis_gap_counts N*4B (mode 0 only)]  — number of gaps per axis stream

All fields documented per rulebook R6 table. Decode is deterministic from header alone.

Constants:
  MAGIC: 4 bytes identifying Cubrim v1 format
  VERSION: 1 (v1)
  MODE_CUBE = 0
  MODE_RAW = 1
  MAP_SCHEME_RLE = 1
  VALUE_SCHEME_FIXED = 1
  TRAVERSAL_LEX = 1
  PHI_MIXED_RADIX = 1
"""

import struct

# Format identification
MAGIC = b"\xCBRIM"   # 4 bytes: 0xCB + "RIM"
VERSION = 1

# Mode constants (R6/R7)
MODE_CUBE = 0
MODE_RAW = 1

# Scheme identifiers (R4, R5)
MAP_SCHEME_RLE = 1
MAP_SCHEME_PACKED_NIBBLE = 2
VALUE_SCHEME_FIXED = 1
VALUE_SCHEME_RLE_CODES = 2
VALUE_SCHEME_ENTROPY = 3

# Traversal and Phi identifiers (R1)
TRAVERSAL_LEX = 1
PHI_MIXED_RADIX = 1

# Fixed-size portion of header (always present)
_FIXED_STRUCT = struct.Struct(">4sBBBHL")
# magic(4s), version(B), mode(B), N(B), B(H=uint16), L(I=uint32)
_FIXED_SIZE = _FIXED_STRUCT.size  # 4+1+1+1+2+4 = 13 bytes


def serialize_header(
    mode: int,
    N: int,
    B: int,
    L: int,
    count: int = 0,
    b_k: list[int] | None = None,
    map_scheme: int = MAP_SCHEME_RLE,
    W: int = 0,
    inverse_dict: list[int] | None = None,
    axis_gap_counts: list[int] | None = None,
    value_scheme: int = VALUE_SCHEME_FIXED,
) -> bytes:
    """
    R6: Serialize header to bytes.

    For mode=1 (raw-store): only fixed fields + L are meaningful.
    For mode=0 (cube): all fields required.
    """
    fixed = _FIXED_STRUCT.pack(MAGIC, VERSION, mode, N, B, L)

    if mode == MODE_RAW:
        return fixed

    # mode == MODE_CUBE: append cube-specific fields
    if b_k is None:
        b_k = [B] * N
    if inverse_dict is None:
        inverse_dict = []
    if axis_gap_counts is None:
        axis_gap_counts = [0] * N

    n_distinct = len(inverse_dict)

    # Pack variable-length fields
    bk_bytes = struct.pack(f">{N}H", *b_k)  # uint16: b_k <= B (B may be 256, which does not fit in uint8)
    schemes = struct.pack(">BBB", map_scheme, value_scheme, W)
    n_dist_bytes = struct.pack(">H", n_distinct)
    # inverse_dict uses uint8 (values are bytes 0..255) — halves dict overhead
    inv_dict_bytes = struct.pack(f">{n_distinct}B", *inverse_dict) if n_distinct else b""
    traversal_phi = struct.pack(">BB", TRAVERSAL_LEX, PHI_MIXED_RADIX)
    count_bytes = struct.pack(">I", count)
    gap_count_bytes = struct.pack(f">{N}H", *axis_gap_counts)  # uint16: axis unique coords <= B=256

    return (fixed + count_bytes + bk_bytes + schemes + n_dist_bytes +
            inv_dict_bytes + traversal_phi + gap_count_bytes)


def parse_header(data: bytes) -> tuple[dict, int]:
    """
    R6: Parse header from bytes. Returns (header_dict, offset_after_header).

    Raises ValueError for invalid magic or unsupported version.
    Raises struct.error for truncated data.
    """
    if len(data) < _FIXED_SIZE:
        raise ValueError(
            f"Data too short to contain header: {len(data)} < {_FIXED_SIZE} bytes"
        )

    magic, version, mode, N, B, L = _FIXED_STRUCT.unpack_from(data, 0)
    offset = _FIXED_SIZE

    if magic != MAGIC:
        raise ValueError(
            f"Invalid magic bytes: {magic!r}, expected {MAGIC!r}. "
            "Not a Cubrim v1 file or corrupt header."
        )
    if version != VERSION:
        raise ValueError(
            f"Unsupported version: {version}. Only version {VERSION} is supported."
        )

    hdr = {
        "magic": magic,
        "version": version,
        "mode": mode,
        "N": N,
        "B": B,
        "L": L,
    }

    if mode == MODE_RAW:
        return hdr, offset

    if mode != MODE_CUBE:
        raise ValueError(f"Unknown mode: {mode}. Expected {MODE_CUBE} or {MODE_RAW}.")

    # Parse cube-specific fields
    # count (4B)
    (count,) = struct.unpack_from(">I", data, offset)
    offset += 4

    # b_k (N * 2B) — uint16, b_k <= B (B=256 does not fit in uint8)
    b_k = list(struct.unpack_from(f">{N}H", data, offset))
    offset += N * 2

    # map_scheme (1B), value_scheme (1B), W (1B)
    map_scheme, value_scheme, W = struct.unpack_from(">BBB", data, offset)
    offset += 3

    # n_distinct (2B)
    (n_distinct,) = struct.unpack_from(">H", data, offset)
    offset += 2

    # inverse_dict (n_distinct * 1B) — byte values 0..255, stored as uint8
    if n_distinct > 0:
        inverse_dict = list(struct.unpack_from(f">{n_distinct}B", data, offset))
        offset += n_distinct * 1
    else:
        inverse_dict = []

    # traversal (1B), phi_id (1B)
    traversal, phi_id = struct.unpack_from(">BB", data, offset)
    offset += 2

    # axis_gap_counts (N * 2B) — uint16, unique coords per axis <= B=256
    axis_gap_counts = list(struct.unpack_from(f">{N}H", data, offset))
    offset += N * 2

    hdr.update({
        "count": count,
        "b_k": b_k,
        "map_scheme": map_scheme,
        "value_scheme": value_scheme,
        "W": W,
        "n_distinct": n_distinct,
        "inverse_dict": inverse_dict,
        "traversal": traversal,
        "phi_id": phi_id,
        "axis_gap_counts": axis_gap_counts,
    })

    return hdr, offset
