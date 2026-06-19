# CUBR-0020 AC-2 — BWT Pre-pass Conditional Entropy Probe

**Generated:** 2026-06-19
**Python:** 3.14.4  **NumPy:** 2.4.6
**Corpus manifest:** `/Users/ug/arcanada/Projects/Cubrim/docs/ephemeral/research/corpus/manifest.json`
**Manifest SHA-256:** `4ee979f3bba94589feaa892949bcf92750e7e1b1cb1f1a2aa6c36dab6c5426b3`

## Methodology

For each corpus file, the i-order value-code sequence `seq_iorder` is built as
`seq_codes[i] = v2c[data[i]]` (byte-exact to T4 `seq_codes` in `codec.rs`).

Four entropy metrics are measured per file:

| Symbol | Definition | Pipeline it proxies |
|--------|-----------|--------------------|
| `H1_iorder` | `cond_entropy_h1(seq_iorder)` | T4 incumbent (order-1, i-order) |
| `H0_iorder` | `entropy_h0(seq_iorder)` | Reference order-0 |
| `H1_bwt` | `cond_entropy_h1(bwt_forward(seq_iorder))` | BWT → order-1 coding |
| `H0_bwt_mtf` | `entropy_h0(mtf_encode(bwt_forward(seq_iorder)))` | BWT → MTF → order-0 (bzip2 path) |

BWT variant: primary-index (no sentinel). Single whole-stream block. Naive O(n² log n) rotation sort — acceptable for n ≤ 65536 in this probe.

**Round-trip invariant:** `bwt_inverse(bwt_forward(seq)) == seq` is asserted for all 7 files before any entropy measurement. A failure aborts the probe.

## Results

Relative reductions are computed against `H1_iorder` (T4 baseline). Positive = improvement over incumbent; negative = regression.

| File | L | n_dist | rho | H0_iorder | H1_iorder | H1_bwt | H0_bwt_mtf | Δbwt-H1 rel | Δbwt-mtf rel |
|------|---|--------|-----|-----------|-----------|--------|------------|------------|-------------|
| sparse_clustered | 2048 | 12 | 0.0312 | 3.3648 | 0.1779 | 0.3281 | 0.3612 | -84.4% | -103.0% |
| dense | 4096 | 256 | 0.0625 | 7.9582 | 3.9849 | 3.9719 | 7.9502 | +0.3% | -99.5% |
| text | 16384 | 27 | 0.2500 | 4.4475 | 2.1257 | 0.7288 | 0.7001 | +65.7% | +67.1% |
| log_like | 16384 | 53 | 0.2500 | 4.8525 | 1.8348 | 0.1574 | 0.2242 | +91.4% | +87.8% |
| binary_mixed | 8192 | 256 | 0.1250 | 7.0936 | 3.2720 | 3.3629 | 5.9285 | -2.8% | -81.2% |
| random_high | 4096 | 256 | 0.0625 | 7.9556 | 3.9877 | 3.9880 | 7.9538 | -0.0% | -99.5% |
| sparse_small | 256 | 4 | 0.0039 | 1.9265 | 0.2743 | 0.4392 | 0.4856 | -60.1% | -77.0% |

## Decision Checkpoint (AC-2)

**Verdict: GO**

H1_bwt (BWT order-1) reduces entropy by 91.4% relative on 'log_like' (H: 1.8348 -> 0.1574 bits). Threshold 5% met. Proceed to Rust implementation (AC-3/AC-4).

**Proxy caveat:** conditional/marginal entropy is a proxy for the real coded size.
A reduction is necessary but not sufficient — the Rust bench (AC-3/AC-4) is ground truth.
This gate exists to avoid writing Rust against an unmeasured win.
