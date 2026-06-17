"""
Cubrim prototype — mixed-radix index-to-coordinates bijection.

# R1: N-dimensional cube with bounded edge, mixed-radix Phi (v1-default).

Phi: index i in [0, L-1] --> coordinates (x_0, x_1, ..., x_{N-1})
  where x_k = (i // B^k) mod B  (mixed-radix base-B decomposition)
  and N = ceil(log_B(L)) or a fixed N=2.

Phi^{-1}: (x_0, ..., x_{N-1}) --> i = sum(x_k * B^k)

v1-default: N=2, B=256.
  Phi is trivially bijective; inversion is exact; round-trip is guaranteed by
  construction (PRD §4.1, OQ-1).

Resolution criterion (OQ-1/OQ-3): a Phi giving higher locality (fraction of gap=1,
longer RLE runs) on the corpus beats this baseline (challengers: Morton/Z-order,
Hilbert curve). Until measured, mixed-radix is the defensible minimum.
"""

import math

# v1-default constants
B_DEFAULT: int = 256
N_DEFAULT: int = 2


def phi(index: int, N: int = N_DEFAULT, B: int = B_DEFAULT) -> tuple[int, ...]:
    """
    R1: Mixed-radix decomposition of index into N coordinates, base B.

    phi(i) = (i mod B, (i // B) mod B, ..., (i // B^{N-1}) mod B)

    Bijective on [0, B^N - 1].
    """
    if index < 0:
        raise ValueError(f"index must be non-negative, got {index}")
    coords = []
    remainder = index
    for _ in range(N):
        coords.append(remainder % B)
        remainder //= B
    return tuple(coords)


def phi_inv(coords: tuple[int, ...], B: int = B_DEFAULT) -> int:
    """
    R1: Inverse mixed-radix: coordinates back to index.

    phi_inv((x_0, x_1, ..., x_{N-1})) = sum(x_k * B^k)
    """
    index = 0
    base = 1
    for x in coords:
        if x < 0 or x >= B:
            raise ValueError(f"coordinate {x} out of range [0, {B-1}]")
        index += x * base
        base *= B
    return index


def compute_N_and_B(length: int, B: int = B_DEFAULT) -> tuple[int, int]:
    """
    Compute minimum N such that B^N >= length.
    v1-default is N=2; if length > B^2, N grows accordingly.
    Returns (N, B).
    """
    if length == 0:
        return (N_DEFAULT, B)
    N = max(N_DEFAULT, math.ceil(math.log(max(length, 1), B)) if length > 1 else 1)
    # Ensure B^N >= length
    while B ** N < length:
        N += 1
    return (N, B)
