# CUBR-0030 — Sparse-Corpus Distance-Map Verdict

**Date:** 2026-06-21
**Task:** CUBR-0030 (Sparse-corpus extension for distance-map lever re-test)
**Branch:** feat/cubr-0030-sparse-corpus
**Code SHA at task start:** 60ae94c

## Verdict: NO-GO

The extended corpus (original 7 files + 2 new both-axis-sparse files) confirms the structural
blocker mathematically predicted in the planning stage (Path B-narrow). The distance-map lever
cannot clear the GO gate under the current position-based phi.

## Numbers

| Metric | Value |
|--------|-------|
| Original T4 aggregate (7 files) | 0.587240 |
| Extended T4 aggregate (9 files) | 0.587560 |
| GO threshold (−2% vs T4) | 0.575495 |
| Best-case hypothetical aggregate | 0.587055 |
| Gap to GO threshold | +0.011560 (needs −1.92%, has +1.95%) |
| Distance-map prior savings (CUBR-0028) | 26 bytes |

## Per-Axis Rho Table (Extended Corpus)

| File | L | ρ (coarse) | ρ_axis0 | ρ_axis1 | ax0_dist | ax1_dist | both_sparse | New |
|------|---|-----------|---------|---------|----------|----------|-------------|-----|
| sparse_clustered | 2048 | 0.031250 | 1.0000 | 0.0312 | 256 | 8 | no | |
| dense | 4096 | 0.062500 | 1.0000 | 0.0625 | 256 | 16 | no | |
| text | 16384 | 0.250000 | 1.0000 | 0.2500 | 256 | 64 | no | |
| log_like | 16384 | 0.250000 | 1.0000 | 0.2500 | 256 | 64 | no | |
| binary_mixed | 8192 | 0.125000 | 1.0000 | 0.1250 | 256 | 32 | no | |
| random_high | 4096 | 0.062500 | 1.0000 | 0.0625 | 256 | 16 | no | |
| sparse_small | 256 | 0.003906 | 1.0000 | 0.0039 | 256 | 1 | no | |
| **both_sparse_16** | **16** | **0.000244** | **0.0625** | **0.0039** | **16** | **1** | **YES** | * |
| **both_sparse_24** | **24** | **0.000366** | **0.0938** | **0.0039** | **24** | **1** | **YES** | * |

The two new files satisfy the both-axis-sparse criterion (rho_axis0 < 0.1 AND rho_axis1 < 0.1)
as literally requested. The coarse rho (L/cube_volume) of 0.000244 and 0.000366 is far below 0.1
on both axes.

## Why the Measurement Confirms NO-GO

**Both-axis-sparse files (L<=25) are near-incompressible and raise the aggregate.**

Adding both_sparse_16 (16 bytes) and both_sparse_24 (24 bytes) pushed the extended T4 aggregate
from 0.587240 → 0.587560 (+0.000320), moving it *away* from the GO threshold. This is expected:
tiny random files are stored at or near raw size in T4 (raw mode = L bytes), contributing
high compression ratios (output / input ≈ 1.0) that drag the weighted aggregate upward.

Even computing the best-case hypothetical (zero distmap cost, apply the 26-byte prior savings
from CUBR-0028 axis-1 measurement):

    hypothetical_aggregate = (30257 - 26) / 51496 = 30231 / 51496 = 0.587055
    GO threshold = 0.575495
    Gap = +0.011560

The gap is **+0.011560** (the aggregate needs to fall 1.96% further to reach GO — but the total
savings from eliminating all distance-map overhead is only ~0.05% of corpus bytes).

## Structural Blocker: Position-Based Phi

Under the current phi implementation (`phi.rs`: `phi(i) = (i % B, i // B)`, B=256, bijective):

```
axis0_distinct(L) = min(L, 256)   →   rho_axis0 = min(L, 256) / 256
axis1_distinct(L) = ceil(L / 256) →   rho_axis1 = ceil(L / 256) / 256
```

Both values are **functions of file length L only** — they are content-blind. The criterion
rho_axis0 < 0.1 AND rho_axis1 < 0.1 translates to:

- rho_axis0 < 0.1  →  L < 25.6  →  **L ≤ 25 bytes**
- rho_axis1 < 0.1  →  ceil(L/256) < 25.6  →  always 1 for L ≤ 25  →  rho_axis1 = 1/256 = 0.0039

Both conditions are satisfiable simultaneously **only** when L ≤ 25 bytes. There is no way to
construct a larger file that is both-axis-sparse under position-based phi, regardless of content.
Such tiny files are near-incompressible, so they cannot contribute a GO improvement.

## Gotcha #6 Compliance

The probe charges all 4 decoder branches (same as CUBR-0029):
- Branch A: axis-0 gap stream
- Branch B: axis-1 gap stream
- Branch C: axis-0 count header (2 bytes)
- Branch D: axis-1 count header (2 bytes)

Self-check PASSED on all 9 files: 4 branches = 4 cost terms.

## T4 Assumption for New Files

No Rust compilation was performed (spike-gate: no src change unless GO). T4 bytes for the new
files are modelled as conservative raw mode (t4_bytes = L). This is the correct bound for
near-incompressible random bytes: T4 raw mode stores the data verbatim when cube encoding
cannot improve.

## The Only GO-Capable Path: Content-Derived Phi (CUBR-0032)

If phi coordinates were derived from **byte value** rather than **position** (e.g. for an
alphabet of size K, phi maps the K distinct values to K cube cells regardless of file length),
then both-axis-sparse would depend on the number of distinct values in the file — not its length.
A file with few distinct byte values (K ≪ 256) would have genuinely sparse axes regardless of L.

This requires changes to:
- `phi.rs` / `phi_inv` (content-derived coordinate mapping)
- `cube.rs` (cube construction from value-to-coord map)
- `distance_map.rs` (gap encoding over value-coord axes)
- Round-trip invariant (CUBR-0001) must be re-proved for the new mapping

This is an R1 rulebook change requiring a consilium design round. It is explicitly out of scope
for this L2 spike and has been filed as **backlog CUBR-0032** (Content-derived-phi distance-map
feasibility, L3, consilium-gated).

## Summary

| Check | Result |
|-------|--------|
| ≥2 both-axis-sparse files generated | PASS (both_sparse_16, both_sparse_24) |
| Per-axis rho < 0.1 on new files | PASS (rho_axis0=0.0625/0.0938, rho_axis1=0.0039) |
| Probe executed on real bytes | PASS (not modelled) |
| Gotcha #6 (4 branches = 4 cost terms) | PASS |
| Aggregate vs GO threshold | NO-GO (0.587055 vs 0.575495, gap +0.011560) |
| No Rust src change | PASS |
| No merge/push to main | PASS |
| CUBR-0032 filed in backlog | PASS |
