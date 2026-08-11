#!/usr/bin/env python3
"""
CUBR-0030 — Synthetic both-axis-sparse corpus generator.

Under position-based phi (phi(i) = (i % B, i // B), B=256):
  axis0_distinct = min(L, 256)   rho_axis0 = axis0_distinct / 256
  axis1_distinct = ceil(L / 256) rho_axis1 = axis1_distinct / 256

Both-axis-sparse (rho_axis0 < 0.1 AND rho_axis1 < 0.1) requires:
  axis0_distinct < 0.1 * 256 = 25.6  -> L < 26 (i.e. L <= 25)
  axis1_distinct < 0.1 * 256 = 25.6  -> ceil(L/256) < 25.6 -> always 1 for L <= 25

Files generated:
  both_sparse_16.bin  L=16  rho_axis0=0.0625, rho_axis1=0.0039 (1/256)
  both_sparse_24.bin  L=24  rho_axis0=0.0938, rho_axis1=0.0039 (1/256)

These are the ONLY files under position-based phi that can satisfy both-axis rho<0.1.
At L=25: rho_axis0=0.0977, rho_axis1=0.0039 — still both < 0.1 (marginal).
At L=26: axis0_distinct=26 -> rho_axis0=0.1016 >= 0.1 — fails axis-0 gate.

Structural blocker: this 25-byte ceiling makes the files near-incompressible
(almost no patterns to exploit) and their small size RAISES the aggregate compression
ratio vs T4, not lowers it. See CUBR-0030 verdict for details.

Seed convention: 8001 for both_sparse_16, 8002 for both_sparse_24 (extending
the manifest seed sequence 1001..7001).
"""

import hashlib
import json
import math
import os
import random

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "corpus")
MANIFEST_PATH = os.path.join(CORPUS_DIR, "manifest.json")
B = 256
N = 2
CUBE_VOLUME = B ** N  # 65536


def axis_stats(L: int) -> dict:
    """Compute per-axis rho for a file of length L under position-based phi."""
    axis0_distinct = min(L, B)
    axis1_distinct = math.ceil(L / B) if L > 0 else 0
    rho_axis0 = axis0_distinct / B
    rho_axis1 = axis1_distinct / B
    return {
        "axis0_distinct": axis0_distinct,
        "axis1_distinct": axis1_distinct,
        "rho_axis0": rho_axis0,
        "rho_axis1": rho_axis1,
    }


def generate_fixture(name: str, L: int, seed: int) -> dict:
    """Generate a seeded fixture of length L; write to corpus dir; return manifest entry."""
    rng = random.Random(seed)
    data = bytes(rng.randint(0, 255) for _ in range(L))

    path = os.path.join(CORPUS_DIR, name + ".bin")
    with open(path, "wb") as fh:
        fh.write(data)

    sha256 = hashlib.sha256(data).hexdigest()
    stats = axis_stats(L)
    rho = L / CUBE_VOLUME

    print(f"  Generated {name}.bin: L={L}, sha256={sha256[:16]}...")
    print(f"    rho={rho:.6f}, rho_axis0={stats['rho_axis0']:.4f}, rho_axis1={stats['rho_axis1']:.4f}")
    print(f"    axis0_distinct={stats['axis0_distinct']}, axis1_distinct={stats['axis1_distinct']}")
    assert stats["rho_axis0"] < 0.1, f"rho_axis0={stats['rho_axis0']} >= 0.1 — blocker"
    assert stats["rho_axis1"] < 0.1, f"rho_axis1={stats['rho_axis1']} >= 0.1 — blocker"

    return {
        "name": name,
        "seed": seed,
        "size_bytes": L,
        "sha256": sha256,
        "rho": round(rho, 6),
        "rho_axis0": round(stats["rho_axis0"], 6),
        "rho_axis1": round(stats["rho_axis1"], 6),
        "has_nontrivial_gap_mechanism": True,
        "axis_unique_counts": [stats["axis0_distinct"], stats["axis1_distinct"]],
        "path": path,
        # T4 baseline for near-incompressible tiny files: approximated as raw size + 1 byte
        # scheme header (consistent with T4 raw mode overhead model in CUBR-0029 probe).
        # No actual T4 Rust run is performed (no Rust src change per spike-gate),
        # so we use the conservative bound: raw bytes = L (T4 raw mode stores uncompressed
        # data when cube encoding cannot improve). For L<=25, raw mode always wins.
        # This is documented as an assumption in CUBR-0030 verdict.
        "actual_t4_bytes": L,
        "actual_t4_mode": "raw",
        "t4_bytes_assumption": (
            "Conservative bound: raw mode, L bytes. "
            "No Rust run performed (spike-gate: no src change unless GO). "
            "T4 raw mode is the expected winner for near-incompressible L<=25 files."
        ),
    }


def main():
    print("CUBR-0030 — Synthetic both-axis-sparse corpus generator")
    print("=" * 60)
    print(f"B={B}, N={N}, cube_volume={CUBE_VOLUME}")
    print(f"Both-axis-sparse constraint: rho_axis0 < 0.1 AND rho_axis1 < 0.1")
    print(f"Under position-based phi: achievable ONLY for L <= 25 bytes")
    print()

    fixtures = [
        ("both_sparse_16", 16, 8001),
        ("both_sparse_24", 24, 8002),
    ]

    print("Generating fixtures:")
    new_entries = []
    for name, L, seed in fixtures:
        entry = generate_fixture(name, L, seed)
        new_entries.append(entry)
    print()

    # Update manifest
    with open(MANIFEST_PATH, "r") as fh:
        manifest = json.load(fh)

    # Check for duplicates
    existing_names = {e["name"] for e in manifest}
    for entry in new_entries:
        if entry["name"] in existing_names:
            print(f"  WARNING: {entry['name']} already in manifest — skipping duplicate")
            continue
        manifest.append(entry)
        print(f"  Appended {entry['name']} to manifest.json")

    with open(MANIFEST_PATH, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"manifest.json updated ({len(manifest)} entries total)")
    print()
    print("Done. Fixtures are both-axis-sparse under position-based phi.")
    print("Structural note: L<=25 files are near-incompressible and RAISE")
    print("the aggregate compression ratio — honest NO-GO is the expected outcome.")


if __name__ == "__main__":
    main()
