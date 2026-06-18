"""
Cubrim prototype — cube construction and sparse representation.

# R1: N-dimensional cube with bounded edge (R1).
# R2: Sparsity — only populated points stored (R2).

The cube C has dimensions b_0 x b_1 x ... x b_{N-1} where each b_k <= B.
Input S (list of integer values) is mapped to cube coordinates via Phi (R1).
Only populated points P (positions where values exist) are stored.

v1-default:
  - N=2, B=256 (mixed-radix Phi)
  - Traversal: lexicographic order of coordinates (x_0, x_1, ...)
  - b_k = B (all edges at maximum; actual populated range may be less)

The cube stores (coordinate tuple -> value) for each input position.
"""

import math
from cubrim_proto.phi import phi, phi_inv, compute_N_and_B, B_DEFAULT, N_DEFAULT


def build_cube(data: bytes, B: int = B_DEFAULT, N: int | None = None) -> dict:
    """
    R1/R2: Build sparse cube from input bytes.

    Returns a dict with:
      - 'N': int — number of dimensions
      - 'B': int — edge bound
      - 'b_k': list[int] — actual edge lengths per axis (all == B in v1)
      - 'L': int — length of input
      - 'populated': list of (coords_tuple, value) in lexicographic order
      - 'count': int — number of populated points |P|
      - 'density': float — rho = count / product(b_k)
    """
    L = len(data)
    N_min, B = compute_N_and_B(L, B)

    if L == 0:
        N_use = N if N is not None else N_DEFAULT
        return {
            "N": N_use,
            "B": B,
            "b_k": [B] * N_use,
            "L": 0,
            "populated": [],
            "count": 0,
            "density": 0.0,
        }

    # N override: clamp to at least N_min for injectivity
    N_use = max(N_min, N) if N is not None else N_min
    b_k = [B] * N_use  # v1: all edges at max B

    # Build coordinate -> value mapping
    # Using lexicographic position (Phi maps index -> coords)
    points: list[tuple[tuple[int, ...], int]] = []
    for i, val in enumerate(data):
        coords = phi(i, N=N_use, B=B)
        points.append((coords, val))

    # Sort by lexicographic order of coordinates (x_0, x_1, ...)
    points.sort(key=lambda p: p[0])

    cube_volume = B ** N_use
    density = L / cube_volume

    return {
        "N": N_use,
        "B": B,
        "b_k": b_k,
        "L": L,
        "populated": points,
        "count": L,
        "density": density,
    }


def rebuild_from_cube(cube_data: dict) -> bytes:
    """
    R1/R2 inverse: Reconstruct original byte sequence from sparse cube.

    Uses Phi^{-1} to map coordinates back to original positions.
    """
    populated = cube_data["populated"]
    L = cube_data["L"]
    B = cube_data["B"]

    if L == 0:
        return b""

    # Reconstruct S[i] = value at position i
    result = bytearray(L)
    for coords, val in populated:
        i = phi_inv(coords, B=B)
        if i < L:
            result[i] = val

    return bytes(result)
