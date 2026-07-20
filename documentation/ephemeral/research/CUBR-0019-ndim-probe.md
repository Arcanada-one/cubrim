# CUBR-0019 Phase 1 — N-Dimensional Cube Conditional Entropy Probe

**Generated:** 2026-06-18
**Python:** 3.14.4  **NumPy:** 2.4.4
**Corpus manifest:** `documentation/ephemeral/research/corpus/manifest.json`
**Manifest SHA-256:** `4ee979f3bba94589feaa892949bcf92750e7e1b1cb1f1a2aa6c36dab6c5426b3`

## Methodology

For each N in the sweep list, the value-code sequence is built in **i-order**:
```
seq_codes[i] = v2c[data[i]]  for i = 0..L-1
```
This matches codec.rs lines 247-262: values are stored at `idx_to_code[phi_inv(coords,b)]`
then read back linearly. Since `phi_inv(phi(i,b,N), b) == i` for any N, the sequence
is always i-order regardless of N.

**Key architectural fact:** The i-order read-back makes seq_codes N-invariant.
H(X_t|X_{t-1}) should be identical across all N (within floating-point precision).

Run-length stats (avg_run, max_run) are computed once per file (N-invariant).

**Fidelity:** i-order seq_codes = T4 stream (CUBR-0018 verified; same functions reused).

**n_min column:** `ceil(log_256(L))`. When N < n_min, the cube has fewer cells than L,
triggering the injectivity guard (raw-store fallback). Marked as `clamped=yes`.

## Results: H(X_t|X_{t-1}) per N per File

| File | L | n_distinct | rho | n_min | avg_run | max_run | H(N=2) clamped? | H(N=3) clamped? | H(N=4) clamped? | H(N=5) clamped? | H(N=6) clamped? |
|------|---|-----------|-----|-------|---------|--------||---------||---------||---------||---------||---------||
| sparse_clustered | 2048 | 12 | 0.03125 | 2 | 48.76 | 100 | 0.177927 no | 0.177927 no | 0.177927 no | 0.177927 no | 0.177927 no |
| dense | 4096 | 256 | 0.0625 | 2 | 1.01 | 2 | 3.984945 no | 3.984945 no | 3.984945 no | 3.984945 no | 3.984945 no |
| text | 16384 | 27 | 0.25 | 2 | 1.00 | 2 | 2.125689 no | 2.125689 no | 2.125689 no | 2.125689 no | 2.125689 no |
| log_like | 16384 | 53 | 0.25 | 2 | 1.02 | 2 | 1.834836 no | 1.834836 no | 1.834836 no | 1.834836 no | 1.834836 no |
| binary_mixed | 8192 | 256 | 0.125 | 2 | 1.47 | 126 | 3.271965 no | 3.271965 no | 3.271965 no | 3.271965 no | 3.271965 no |
| random_high | 4096 | 256 | 0.0625 | 2 | 1.00 | 2 | 3.987698 no | 3.987698 no | 3.987698 no | 3.987698 no | 3.987698 no |
| sparse_small | 256 | 4 | 0.003906 | 1 | 23.27 | 35 | 0.274312 no | 0.274312 no | 0.274312 no | 0.274312 no | 0.274312 no |

## N-Invariance Analysis

| File | H(N=2) | H(N=max) | max |H_N - H_2| | max_rel % |
|------|--------|----------|------------|-----------|
| sparse_clustered | 0.17792725 | 0.17792725 | 0.00e+00 | 0.0000% |
| dense | 3.98494459 | 3.98494459 | 0.00e+00 | 0.0000% |
| text | 2.12568887 | 2.12568887 | 0.00e+00 | 0.0000% |
| log_like | 1.83483645 | 1.83483645 | 0.00e+00 | 0.0000% |
| binary_mixed | 3.27196488 | 3.27196488 | 0.00e+00 | 0.0000% |
| random_high | 3.98769838 | 3.98769838 | 0.00e+00 | 0.0000% |
| sparse_small | 0.27431226 | 0.27431226 | 0.00e+00 | 0.0000% |

**Overall max |H_N - H_2|:** 0.00e+00 bits (floating-point rounding only).

This confirms the structural prediction: `seq_codes` is i-order for all N by construction,
so H(X_t|X_{t-1}) is N-invariant.

## Run-Length Statistics

Run-length stats are identical across N (same seq_codes):

| File | avg_run | max_run |
|------|---------|---------|
| sparse_clustered | 48.7619 | 100 |
| dense | 1.0056 | 2 |
| text | 1.0029 | 2 |
| log_like | 1.0241 | 2 |
| binary_mixed | 1.4705 | 126 |
| random_high | 1.0034 | 2 |
| sparse_small | 23.2727 | 35 |

## Fidelity Assertion

**Status: PASS**

N=2 H matches i-order reference for all files (max delta=0.00e+00). Since CUBR-0018 confirmed i-order == T4 seq_codes, fidelity to T4 is established.

## Decision Checkpoint (AC-2)

**Verdict: NO-GO**

seq_codes is built via phi_inv → idx_to_code → linear read (i-order). phi_inv(phi(i, b, N), b) == i for all valid N, so idx_to_code[i] always holds v2c[data[i]] regardless of N. Max relative H variation across N=2,3,4,5,6: 0.0000% (threshold 5%). H(X_t|X_{t-1}) is N-invariant by construction. NO-GO: Phase 2 Rust bench is n/a. Finding deepens Gotcha #2: not only does the distance-map weight fail to vary meaningfully with N, the T4 value-stream conditional entropy is also N-invariant.

## Relationship to Gotcha #2

CUBR-0012 showed that the distance-map (gap mechanism) weight is inert w.r.t. N under
order-0 coding. CUBR-0019 now shows that the T4 value-stream conditional entropy is also
N-invariant — because seq_codes is built in i-order regardless of N.

Both the gap stream and the value stream are N-invariant in the current architecture.
The lever for T4 improvement does NOT lie in varying N. It would require a different
value-stream serialization order (not i-order) to make H depend on N — that is a
separate hypothesis (Idea 3 BWT pre-pass / CUBR-0020).

**Proposed Gotcha #5** (single-file Class A edit to CLAUDE.md): T4 value-stream is
N-invariant under i-order coding (phi_inv → idx_to_code → linear read). Confirmed.
