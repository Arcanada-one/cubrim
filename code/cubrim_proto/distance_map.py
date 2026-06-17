"""
Cubrim prototype — per-axis gap-to-next distance map.

# R3: Distance map (gap-to-next) encoding for populated point coordinates.
# R3.1: Sentinel -1 start; gap=1 means zero skipped slots.

For each axis k, given the sorted coordinates of populated points along that axis,
encode as gaps from sentinel x_k = -1:

  gap_k^{(j)} = x_k^{(j)} - x_k^{(j-1)}    where x_k^{(-1)} = -1 (sentinel)

Invariant (fail-closed):
  1 <= gap_k <= b_k <= B
  gap=0 is forbidden (two points cannot share the same slot in traversal order).
  gap > b_k is forbidden (skip cannot exceed edge length).

Decode: start at x_k = -1, then x_k += gap_k for each gap.

Worked example (rulebook R3.1 §4.7, 1D, b_k=8):
  populated {0, 3, 7}
  gaps: 0-(-1)=1, 3-0=3, 7-3=4  →  D = (1, 3, 4)
  decode: -1+1=0, 0+3=3, 3+4=7  →  {0, 3, 7}  ✓
"""


def validate_gaps(gaps: list[int], b_k: int) -> None:
    """
    R3.1: Validate gap sequence invariant: 1 <= gap <= b_k for all gaps.
    Raises ValueError on violation.
    """
    for i, g in enumerate(gaps):
        if g < 1:
            raise ValueError(
                f"gap invariant violated: gap[{i}]={g} < 1 "
                f"(gap=0 forbidden; sentinel=-1 means gap=1 for slot 0)"
            )
        if g > b_k:
            raise ValueError(
                f"gap invariant violated: gap[{i}]={g} > b_k={b_k} "
                f"(gap exceeds edge length)"
            )


def encode_axis_gaps(coords: list[int], b_k: int) -> list[int]:
    """
    R3/R3.1: Encode sorted coordinate list to gap sequence.

    Sentinel x_k = -1 (virtual position before slot 0).
    gap_k^{(j)} = coords[j] - coords[j-1]  (with coords[-1] = -1)

    Invariant checks (fail-closed):
      - coords must be strictly monotone (sorted ascending, no duplicates)
      - all coords in [0, b_k-1]
      - resulting gaps must satisfy 1 <= gap <= b_k
    """
    if not coords:
        return []

    # Validate coordinates are in range
    for c in coords:
        if c < 0 or c >= b_k:
            raise ValueError(
                f"coordinate {c} out of range [0, {b_k - 1}] for b_k={b_k}"
            )

    gaps = []
    prev = -1  # sentinel
    for c in coords:
        g = c - prev
        if g <= 0:
            raise ValueError(
                f"gap invariant violated: gap={g} <= 0 at coord={c} (prev={prev}). "
                f"Coordinates must be strictly increasing (no duplicates). "
                f"Detected: coords={coords}"
            )
        if g > b_k:
            raise ValueError(
                f"gap invariant violated: gap={g} > b_k={b_k} at coord={c}. "
                f"Coordinate out of valid range for edge length b_k={b_k}."
            )
        gaps.append(g)
        prev = c

    return gaps


def decode_axis_gaps(gaps: list[int]) -> list[int]:
    """
    R3.1 inverse: Decode gap sequence back to coordinate list.

    Start: x_k = -1 (sentinel).
    For each gap: x_k += gap_k.
    """
    coords = []
    x = -1  # sentinel start
    for g in gaps:
        x += g
        coords.append(x)
    return coords


def encode_distance_map(cube_data: dict) -> dict:
    """
    R3/R3.1: Build N-stream distance map from cube populated points.

    For each axis k, extract the sorted unique coordinates of populated points
    on that axis and encode as gap sequences.

    Returns:
      {
        'N': int,
        'b_k': list[int],
        'axis_gaps': list[list[int]],   # one gap list per axis
        'axis_coords': list[list[int]], # original coords per axis (for verify)
        'point_coords': list[tuple],    # all point coordinate tuples in order
        'values': list[int],            # corresponding values
      }
    """
    N = cube_data["N"]
    b_k = cube_data["b_k"]
    populated = cube_data["populated"]

    if not populated:
        return {
            "N": N,
            "b_k": b_k,
            "axis_gaps": [[] for _ in range(N)],
            "axis_coords": [[] for _ in range(N)],
            "point_coords": [],
            "values": [],
        }

    # Split populated into (coords_list, values_list) — already in lex order
    point_coords = [p[0] for p in populated]
    values = [p[1] for p in populated]

    # For each axis, collect all coordinates of populated points in order
    # (duplicates allowed across points sharing a coordinate on this axis)
    # For distance map: we encode per-axis unique sorted coordinates
    # BUT to reconstruct exact points we need the full per-point axis values.
    # v1: encode per-axis gap sequence over ALL point coords (with duplicates = adjacent equal)
    # The gap stream has one entry per populated point per axis.

    axis_gaps = []
    axis_coords = []

    for k in range(N):
        coords_k = [p[k] for p in point_coords]
        # Encode gaps — coords_k may contain duplicates (multiple points with same x_k)
        # Adjacent duplicates → gap = 0 would occur, which violates R3.1.
        # Solution: encode the coordinate sequence INCLUDING repetitions using
        # "same position = gap 0" — but R3.1 forbids gap=0.
        #
        # The correct interpretation for the distance map:
        # We encode the SORTED UNIQUE axis coordinates for each axis separately,
        # then reconstruct point membership via value stream ordering.
        # This is the N-streams layout from the plan.
        unique_coords_k = sorted(set(coords_k))
        gaps_k = encode_axis_gaps(unique_coords_k, b_k[k])
        axis_gaps.append(gaps_k)
        axis_coords.append(unique_coords_k)

    return {
        "N": N,
        "b_k": b_k,
        "axis_gaps": axis_gaps,
        "axis_coords": axis_coords,
        "point_coords": point_coords,
        "values": values,
    }


def decode_distance_map(dm: dict) -> list[tuple[int, ...]]:
    """
    R3.1 inverse: Recover per-axis unique coordinates from gap sequences.
    Returns list of unique coord lists per axis.
    """
    N = dm["N"]
    axis_gaps = dm["axis_gaps"]
    axis_coords_recovered = []
    for k in range(N):
        coords_k = decode_axis_gaps(axis_gaps[k])
        axis_coords_recovered.append(coords_k)
    return axis_coords_recovered
