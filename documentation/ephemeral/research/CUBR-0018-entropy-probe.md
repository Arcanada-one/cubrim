# CUBR-0018 Phase 1 — Axis-Traversal Conditional Entropy Probe

**Generated:** 2026-06-18
**Python:** 3.14.4  **NumPy:** 2.4.4
**Corpus manifest:** `docs/ephemeral/research/corpus/manifest.json`
**Manifest SHA-256:** `4ee979f3bba94589feaa892949bcf92750e7e1b1cb1f1a2aa6c36dab6c5426b3`

## Methodology

For each corpus file, three value-code sequences are built:
- **i-order**: `seq_codes[i] = v2c[data[i]]` (i = 0..L-1) — matches Rust T4 `seq_codes`
- **axis-0-sorted**: positions sorted by `phi(i)[0] = i % 256` (stable sort)
- **axis-1-sorted**: positions sorted by `phi(i)[1] = i // 256` (stable sort)

Phi mapping matches `phi.rs` exactly: `phi(i) = (i % 256, i // 256)` for N=2, B=256.

Conditional entropy H(Xt|Xt-1) is computed from empirical bigram counts.
Sentinel context 0 is used for position 0 (matches T4 `prev_ctx = 0` initialisation).

**Fidelity:** The i-order sequence produced here is byte-exact to the `seq_codes`
vector built in `codec.rs` `encode_with_config` (lines 247-262).

## Results Table

| File | L | n_distinct | rho | H(i-order) | H(ax0-sorted) | H(ax1-sorted) | delta-ax0 rel | delta-ax1 rel |
|------|---|-----------|-----|-----------|--------------|--------------|--------------|--------------|
| sparse_clustered | 2048 | 12 | 0.03125 | 0.1779 | 2.2872 | 0.1779 | -1185.5% | +0.0% |
| dense | 4096 | 256 | 0.0625 | 3.9849 | 3.9808 | 3.9849 | +0.1% | +0.0% |
| text | 16384 | 27 | 0.25 | 2.1257 | 4.4187 | 2.1257 | -107.9% | +0.0% |
| log_like | 16384 | 53 | 0.25 | 1.8348 | 3.4084 | 1.8348 | -85.8% | +0.0% |
| binary_mixed | 8192 | 256 | 0.125 | 3.2720 | 4.6833 | 3.2720 | -43.1% | +0.0% |
| random_high | 4096 | 256 | 0.0625 | 3.9877 | 3.9885 | 3.9877 | -0.0% | +0.0% |
| sparse_small | 256 | 4 | 0.003906 | 0.2743 | 0.2743 | 0.2743 | +0.0% | +0.0% |

## Structural Analysis

**Why axis-0-sort is harmful, not neutral:**

For the Cubrim phi mapping with N=2, B=256, coord0 = i%256 and coord1 = i//256.

- For `sparse_clustered` (L=2048, rho=0.03125): data has 42 i-order runs with avg length 48.8.
  Values are spatially clustered in consecutive positions (positions 0..100 share a value, etc.).
  Axis-0-sort groups positions {0, 256, 512, 768, 1024, 1280, 1536, 1792} together first,
  then {1, 257, 513, ...} — these are maximally scattered. Result: 1886 runs, avg 1.1
  (essentially random order). Entropy explodes from 0.1779 to 2.2872 bits (-1186%).

- For axis-1-sort: coord1 = i//256, so positions 0..255 all have coord1=0, positions 256..511
  have coord1=1, etc. Stable sort by coord1 = same block order = IDENTICAL to i-order
  for L<=65536. All files in this corpus have L<=16384, so axis-1-sort equals i-order exactly.

**Root cause:** the corpus data is clustered by original index (i-order), not by phi-coordinate.
The phi mapping is NOT a locality-preserving transform — it scatters spatially adjacent inputs
to different parts of the cube. Sorting by cube coordinate therefore destroys the original
spatial locality that T4 exploits. The correlation structure lives in i-space, not in phi-space.

## Decision Checkpoint (AC-2)

**Verdict: NO-GO**

Best relative reduction: ax0=+0.1% on `dense` (only file with marginal gain, not significant),
ax1=+0.0% across all files. Axis-0-sort is actively harmful on clustered files.
Neither traversal meets the 5% threshold on any file.

**Root reason:** axis-sort destroys the spatial locality of i-order that the T4 order-1 context
already exploits. The correlation structure of the corpus lives in input-index space, not in
phi-coordinate space. Axis-sorted traversal is the wrong model for this corpus.

**Wish-3 status:** n/a — gate did not pass; Phase 2 Rust implementation is skipped.
This is a valid research outcome per plan NO-GO path.

**Proxy caveat:** conditional entropy is a proxy for the real T4 coded size. A reduction
is necessary but not sufficient — the Rust bench in Phase 2 is the ground truth. The gate
exists to avoid writing Rust against an unmeasured win.
