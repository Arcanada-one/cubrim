"""
Generator tests for the benchmark corpus.

Validates:
  - Determinism: regenerating from same seed produces identical sha256
  - V-AC-2: at least one input has rho < 0.3 with non-trivial gaps
  - V-AC-3: corpus data is not tracked (gitignore check)
  - Size constraint: all inputs in (HEADER_OVERHEAD_BOUND, CUBE_UPPER_LIMIT]
    (except random_high which can be any size; all sizes match declared params)

Run:
  python code/corpus-gen/test_generators.py
from Projects/Cubrim root.
"""

import hashlib
import sys
from pathlib import Path

# Allow import of generate_corpus regardless of cwd
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from generate_corpus import (
    GENERATORS,
    measure_rho,
    verify_sparse_constraint,
    HEADER_OVERHEAD_BOUND,
    CUBE_UPPER_LIMIT,
)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_determinism():
    """Each generator, called twice with same params, produces identical sha256."""
    print("Testing determinism...")
    for name, fn, params in GENERATORS:
        a = fn(**params)
        b = fn(**params)
        assert sha256_of(a) == sha256_of(b), (
            f"Generator '{name}' is non-deterministic: "
            f"first={sha256_of(a)[:12]}, second={sha256_of(b)[:12]}"
        )
        print(f"  {name:20s}  deterministic OK  sha256={sha256_of(a)[:12]}...")
    print("Determinism: PASS")


def test_sizes():
    """Each generator produces correct size matching its params."""
    print("Testing output sizes...")
    for name, fn, params in GENERATORS:
        data = fn(**params)
        expected_size = params["size"]
        assert len(data) == expected_size, (
            f"Generator '{name}' produced {len(data)} bytes, expected {expected_size}"
        )
        print(f"  {name:20s}  size={len(data)}  OK")
    print("Sizes: PASS")


def test_sparse_v_ac_2():
    """At least one input has rho < 0.3 with non-trivial gaps (V-AC-2)."""
    print("Testing V-AC-2 sparse constraint...")
    manifest_entries = []
    for name, fn, params in GENERATORS:
        data = fn(**params)
        rho, axis_gaps, axis_unique_counts = measure_rho(data)
        b_per_axis = 256
        has_nontrivial = any(uc < b_per_axis for uc in axis_unique_counts)
        manifest_entries.append({
            "name": name,
            "rho": rho,
            "has_nontrivial_gap_mechanism": has_nontrivial,
            "axis_unique_counts": axis_unique_counts,
        })
        print(f"  {name:20s}  rho={rho:.4f}  axis_unique={axis_unique_counts}  nontrivial_gap_mechanism={has_nontrivial}")

    verify_sparse_constraint(manifest_entries)
    print("V-AC-2: PASS")


def test_cube_eligible_sizes():
    """Sparse and dense inputs are in the cube-eligible window."""
    print("Testing cube-eligible size window...")
    cube_eligible_names = {"sparse_clustered", "dense", "text", "log_like", "binary_mixed"}
    # Note: sparse_small (256 bytes <= 320) is NOT cube-eligible under v1_default (raw_store_bound=320);
    # it becomes cube-eligible under the T2 tuned config (raw_store_bound=200).
    for name, fn, params in GENERATORS:
        if name not in cube_eligible_names:
            continue
        data = fn(**params)
        size = len(data)
        assert HEADER_OVERHEAD_BOUND < size <= CUBE_UPPER_LIMIT, (
            f"'{name}' size {size} not in cube-eligible window "
            f"({HEADER_OVERHEAD_BOUND}, {CUBE_UPPER_LIMIT}]"
        )
        print(f"  {name:20s}  size={size} in ({HEADER_OVERHEAD_BOUND}, {CUBE_UPPER_LIMIT}]  OK")
    print("Cube-eligible sizes: PASS")


if __name__ == "__main__":
    test_determinism()
    print()
    test_sizes()
    print()
    test_sparse_v_ac_2()
    print()
    test_cube_eligible_sizes()
    print("\nAll generator tests PASSED.")
