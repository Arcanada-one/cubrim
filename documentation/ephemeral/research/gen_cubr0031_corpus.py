#!/usr/bin/env python3
"""
CUBR-0031 — Block-bound run-heavy corpus generator.

Generates docs/ephemeral/research/corpus/block_bound_runs.bin:
  L = exactly 65536 bytes  (== cube_size_limit = B*B = 256*256)
  seed = 8003

Codec routing constraint (codec.rs:233):
  encode_with_config routes l > cube_size_limit to raw-store fast-path.
  65536 > 65536 is FALSE, so L = 65536 still enters cube/BWT mode.
  L = 65537 would raw-store and defeat the test.

Rho=1 tension (CLAUDE.md Gotcha #1 + task-description §Rho=1):
  At L = 65536 the cube is exactly full (rho = 1.0); all gaps equal 1;
  the distance-map carries zero information.
  The larger-block lever operates on the VALUE-CODE STREAM, not the gap map.
  Fixture run structure must therefore live in the VALUE STREAM:
    - long alternating runs over a SMALL byte set (low entropy)
    - heavy-tailed run lengths (power-law-like)
    - occasional transitions to preserve order-1 context
  NOT pure-random (that would be a strawman for BWT — BWT gains on run structure).

Structure:
  We draw from a small alphabet of k=8 distinct byte values.
  Run lengths are drawn from a heavy-tailed (Pareto-like) distribution:
    P(length = n) ∝ 1/n^alpha, alpha=1.5, capped at max_run=4096.
  Value transitions: after each run, the next value is chosen from
    the alphabet, preferring adjacent values (Markov-chain with strong
    self-transition) to produce order-1 context that BWT can exploit.
  Total L is tracked; the final run is truncated or extended to exactly 65536.

Fair-test note:
  This fixture is deliberately FAVORABLE to BWT — long runs in the value stream
  are exactly what BWT's sorting reorganizes into runs in the transformed output.
  If BWT does not beat T4 on this fixture, it will NOT beat T4 on any real-world
  structured data of this block size.
  A NO-GO result here is a REAL closure of CUBR-0029 Class B #2 (not just modelled).
"""

import hashlib
import json
import os
import random

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "corpus")
MANIFEST_PATH = os.path.join(CORPUS_DIR, "manifest.json")

B = 256
N = 2
CUBE_VOLUME = B ** N  # 65536

L_TARGET = 65536   # exactly cube_size_limit
SEED = 8003


def generate_block_bound_runs(L: int, seed: int) -> bytes:
    """
    Generate a run-heavy value stream of exactly L bytes.

    Alphabet: 8 distinct byte values [10, 30, 50, 70, 90, 110, 130, 150]
    (spread across the byte range so value-codes use a modest spread).

    Run lengths: truncated Pareto alpha=1.5, min=8, max=4096.
    Value transitions: Markov chain with p_self=0.3 (30% chance the next run
    uses the same value — creates long-distance repeats that BWT can exploit),
    otherwise uniform draw from the remaining 7 values.
    """
    rng = random.Random(seed)

    alphabet = [10, 30, 50, 70, 90, 110, 130, 150]
    k = len(alphabet)

    # Pareto run-length: inverse-transform sampling with alpha=1.5, min_run=8, max_run=4096
    alpha = 1.5
    min_run = 8
    max_run = 4096

    def sample_run_length():
        # Inverse CDF of Pareto: L = min_run * (1 - U)^(-1/alpha)
        u = rng.random()
        raw = min_run * ((1.0 - u) ** (-1.0 / alpha))
        return min(max_run, max(min_run, int(raw)))

    data = bytearray()
    current_value_idx = rng.randint(0, k - 1)

    while len(data) < L:
        run_len = sample_run_length()
        remaining = L - len(data)
        actual_run = min(run_len, remaining)
        data.extend([alphabet[current_value_idx]] * actual_run)

        # Markov transition: p_self = 0.3
        if rng.random() < 0.3:
            pass  # stay on same value (creates repeating runs for BWT context)
        else:
            others = [i for i in range(k) if i != current_value_idx]
            current_value_idx = rng.choice(others)

    assert len(data) == L, f"Length mismatch: {len(data)} != {L}"
    return bytes(data)


def run_stats(data: bytes) -> dict:
    """Compute run-length statistics."""
    if not data:
        return {}
    runs = []
    curr = data[0]
    run = 1
    for b in data[1:]:
        if b == curr:
            run += 1
        else:
            runs.append(run)
            curr = b
            run = 1
    runs.append(run)

    avg_run = sum(runs) / len(runs)
    max_run = max(runs)
    min_run = min(runs)
    long_runs = sum(1 for r in runs if r >= 100)
    distinct_values = len(set(data))

    return {
        "num_runs": len(runs),
        "avg_run_length": round(avg_run, 2),
        "max_run_length": max_run,
        "min_run_length": min_run,
        "runs_ge_100": long_runs,
        "distinct_values": distinct_values,
    }


def main():
    print("CUBR-0031 — Block-bound run-heavy corpus generator")
    print("=" * 60)
    print(f"B={B}, N={N}, cube_volume={CUBE_VOLUME}")
    print(f"Target L = {L_TARGET} (== cube_size_limit, enters cube/BWT mode)")
    print(f"Seed = {SEED}")
    print()

    name = "block_bound_runs"
    print(f"Generating {name}.bin ...")
    data = generate_block_bound_runs(L_TARGET, SEED)

    assert len(data) == L_TARGET, f"Length error: {len(data)}"
    sha256 = hashlib.sha256(data).hexdigest()
    rho = L_TARGET / CUBE_VOLUME  # exactly 1.0

    stats = run_stats(data)
    print(f"  L = {len(data)}")
    print(f"  rho = {rho:.6f} (exactly 1.0 — cube full, gaps all = 1)")
    print(f"  sha256 = {sha256[:32]}...")
    print(f"  distinct_values = {stats['distinct_values']}")
    print(f"  num_runs = {stats['num_runs']}")
    print(f"  avg_run_length = {stats['avg_run_length']}")
    print(f"  max_run_length = {stats['max_run_length']}")
    print(f"  min_run_length = {stats['min_run_length']}")
    print(f"  long_runs (>=100) = {stats['runs_ge_100']}")
    print()

    # Write binary
    path = os.path.join(CORPUS_DIR, name + ".bin")
    with open(path, "wb") as fh:
        fh.write(data)
    print(f"  Written to: {path}")
    print()

    # Manifest entry — t4 and bwt bytes are UNKNOWN until Rust codec runs;
    # they are filled in by the bench harness (tests/cubr0031_bench.rs).
    new_entry = {
        "name": name,
        "seed": SEED,
        "size_bytes": L_TARGET,
        "sha256": sha256,
        "rho": round(rho, 6),
        "has_nontrivial_gap_mechanism": False,  # rho=1 → gaps all 1 → gap map trivial
        "rho_note": (
            "rho=1.0 — cube fully populated, all gaps=1, gap map carries zero info. "
            "Compression lever is entirely in the value-code stream (run structure)."
        ),
        "axis_unique_counts": [B, B],  # full cube: axis0=256, axis1=256
        "path": path,
        "run_stats": stats,
        "fair_test_note": (
            "Run-heavy fixture (Pareto alpha=1.5 run lengths, k=8 alphabet, Markov transitions). "
            "Deliberately FAVORABLE to BWT — if BWT does not beat T4 here, no real-world "
            "structured data at this block size will justify the u16->u32 widening."
        ),
        # Filled in by bench harness (cubr0031_bench.rs); placeholder until then
        "actual_t4_bytes": None,
        "actual_bwt_bytes": None,
        "actual_t4_mode": "cube",  # expected: L=65536 >= raw_store_bound default, but scheme byte decides
        "measurement_note": (
            "T4 and BWT bytes to be filled by tests/cubr0031_bench.rs (real codec). "
            "This placeholder must not be used for GO/NO-GO — wait for bench output."
        ),
    }

    # Update manifest
    with open(MANIFEST_PATH, "r") as fh:
        manifest = json.load(fh)

    existing_names = {e["name"] for e in manifest}
    if name in existing_names:
        print(f"  WARNING: {name} already in manifest — updating in place")
        manifest = [e if e["name"] != name else new_entry for e in manifest]
    else:
        manifest.append(new_entry)
        print(f"  Appended {name} to manifest.json")

    with open(MANIFEST_PATH, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"  manifest.json updated ({len(manifest)} entries total)")
    print()

    print("Structure summary:")
    print("  - alphabet: 8 byte values spread across 0-255")
    print("  - run lengths: Pareto alpha=1.5, min=8, max=4096")
    print("  - Markov transitions: p_self=0.30 (repeating runs)")
    print("  - rho=1.0: cube FULL, gaps trivial, lever = value stream only")
    print("  - L=65536: enters cube/BWT mode (NOT raw-store, 65536>65536 is FALSE)")
    print()
    print("Next step: run tests/cubr0031_bench.rs to measure real T4 and BWT bytes.")
    print(f"sha256: {sha256}")


if __name__ == "__main__":
    main()
