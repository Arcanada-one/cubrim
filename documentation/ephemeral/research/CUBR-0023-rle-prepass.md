# CUBR-0023 — RLE Pre-pass on Value-Stream (R4) — Phase A Spike Analysis

**Generated:** 2026-06-19  
**Code SHA:** `794148d85631bc0e2f351e2178d3ab7e7911e137` (main, merged T4 PR)  
**Branch:** `feat/cubr-0023-rle-prepass`  
**Corpus manifest SHA-256:** `cdd613090c7a8b908a6850902554e06d23b8578c7b136bb24ff7fb9fb8fcea94`  
**Probe script:** `docs/ephemeral/research/cubr_0023_rle_probe.py`  
**T4 actuals source:** `CUBR-0017-bench.json` (code SHA `734d540`, same Rust logic as `794148d`)

---

## Hypothesis Under Test

**R4: RLE pre-pass on the value-code stream before order-1 Huffman (T4).**

The hypothesis: if the value-code stream (i-order, T4's input) contains runs of identical bytes, converting them to `(literal | escape+run_length)` tokens before applying T4 order-1 Huffman would yield a shorter output by:
1. Collapsing runs into single literal + optional escape token → shorter token stream
2. Making Huffman context statistics cleaner (no repetitive patterns across context boundaries)

The proposed scheme (T6) uses: side-table of run counts (2B/run-ge-2) + order-1 context Huffman on the token stream with escape symbol added to alphabet.

---

## AC-1 — Run-Length Structure of Value-Stream (i-order)

Value-code sequence extraction: `seq_codes[i] = v2c[data[i]]` for `i in 0..L-1` (matching `codec.rs` lines 247-262, i-order, N-invariant as verified in CUBR-0019).

| File | L | n_dist | rho | n_runs | avg_run | max_run | frac≥2 | frac≥3 | frac≥4 |
|------|---|--------|-----|--------|---------|---------|--------|--------|--------|
| sparse_clustered | 2048 | 12 | 0.0313 | 42 | 48.76 | 100 | 1.000 | 1.000 | 1.000 |
| dense | 4096 | 256 | 0.0625 | 4073 | 1.01 | 2 | 0.011 | 0.000 | 0.000 |
| text | 16384 | 27 | 0.2500 | 16336 | 1.00 | 2 | 0.006 | 0.000 | 0.000 |
| log_like | 16384 | 53 | 0.2500 | 15998 | 1.02 | 2 | 0.047 | 0.000 | 0.000 |
| binary_mixed | 8192 | 256 | 0.1250 | 5571 | 1.47 | 126 | 0.338 | 0.311 | 0.311 |
| random_high | 4096 | 256 | 0.0625 | 4082 | 1.00 | 2 | 0.007 | 0.000 | 0.000 |
| sparse_small | 256 | 4 | 0.0039 | 11 | 23.27 | 35 | 1.000 | 1.000 | 1.000 |

**Key observation:** Only `sparse_clustered` and `sparse_small` have substantial run structure. For the 5 remaining files, the value-code stream is near-singleton (avg_run ≤ 1.47, max_run ≤ 2 except binary_mixed which has max=126 but avg=1.47). Text and log_like — the files where T4 achieves best compression — have essentially no run structure (avg_run≈1.00, frac_ge2 < 5%).

---

## AC-2 — Size Analysis

### Actual encoder sizes (from CUBR-0017-bench.json, same Rust code)

| File | size | T4 actual | T4 mode | T2 (RLE-codes) | T2 mode |
|------|------|-----------|---------|----------------|---------|
| sparse_clustered | 2048 | 502 | cube | 178 | cube |
| dense | 4096 | 4109 | **raw** | 4109 | **raw** |
| text | 16384 | 5705 | cube | 16397 | **raw** |
| log_like | 16384 | 7318 | cube | 16397 | **raw** |
| binary_mixed | 8192 | 8205 | **raw** | 8205 | **raw** |
| random_high | 4096 | 4109 | **raw** | 4109 | **raw** |
| sparse_small | 256 | 269 | **raw** | 269 | **raw** |
| **TOTAL** | **51456** | **30217** | | **49664** | |
| **aggregate** | | **0.587240** | | **0.965174** | |

### Python model for proposed T6 (RLE pre-pass + T4 order-1 Huffman)

The Python model computes value-stream costs using a Python twin of `context_huffman_size` from `codec.rs`. Model accuracy calibration: for `sparse_clustered`, Python overestimates T4 value stream by ~9B (511 model vs 502 actual); for `text`, overestimates by ~354B (6059 vs ~5350 actual value stream). Relative deltas are directionally reliable but magnitudes carry ~5-15% uncertainty.

| File | T4 V-stream (model) | RLE+T4 V-stream (model) | delta vs T4 | T4 mode | T6 full estimate |
|------|---------------------|-------------------------|-------------|---------|-----------------|
| sparse_clustered | 511B | 140B | **-72.6%** | cube | 137B |
| dense | 37990B | 37924B | -0.2% | **raw** | 4109B (raw-store) |
| text | 6059B | 6173B | **+1.9%** | cube | 5812B |
| log_like | 7291B | 8072B | **+10.7%** | cube | 8101B |
| binary_mixed | 23875B | 17233B | -27.8% | **raw** | 8205B (raw-store) |
| random_high | 39735B | 39408B | -0.8% | **raw** | 4109B (raw-store) |
| sparse_small | 69B | 37B | -46.4% | **raw** | 269B (raw-store) |

**Critical finding for raw-stored files:** Dense, binary_mixed, random_high, and sparse_small are all raw-stored by R7 (any value scheme would trigger raw-store since cube-mode overhead exceeds data size). T6 cannot change these files — they remain raw-stored at 4109/8205/4109/269B regardless.

**T6 model aggregate** = 137 + 4109 + 5812 + 8101 + 8205 + 4109 + 269 = **30742B = 0.5974 ratio**  
**vs T4 baseline 30217B = 0.5872 → T6 is +1.74% WORSE in aggregate.**

---

## AC-2b — Why T6 Regresses on Key Files

### Text (the most impactful cube-mode file, 16384B original → 5705B T4)

- Value-code stream: 27 distinct symbols, avg_run=1.003, max_run=2, only ~48 runs of length 2 exist.
- RLE pre-pass on near-singleton data: produces ~16336 literal tokens + 48 escape tokens = 16384 total tokens.
- New escape symbol (28th) added to alphabet → every context table grows by 1 entry.
  - T4 with n_distinct=27: header = 2 + n_ctx × (2+27) bytes per context
  - T6 with n_distinct=28: header = 2 + n_ctx × (2+28) bytes per context
  - If T4 has ~27 qualifying contexts: extra 27 bytes header + 98 bytes side-table for 48 run-2s = +125B minimum.
- Model confirms: +1.88% regression on value stream.

### Log_like (second cube-mode file, 16384B → 7318B T4)

- Similar story: 53 distinct symbols, avg_run=1.024, max=2. ~770 runs of length 2 (frac_ge2=0.047 × 16384 / 2 ≈ 385 runs, 770 codes).
- 385 escape tokens added; side-table = 385 × 2B = 770B.
- New 54th symbol in alphabet → all n_ctx × 1 byte extra in header.
- Model: +10.71% regression — larger because 53 context tables (2 bytes each) plus 770B side-table.

### Sparse_clustered (where T4 loses to T2)

- Rich run structure. T2 (actual 178B) already dominates T4 (actual 502B).
- T6 model says value-stream = 140B < T2 model 126B. But:
  - T2 model (126B) vs T2 actual (178B): model underestimates actual by 41%.
  - T6 model (140B) vs expected actual: same ratio suggests T6 actual ≈ 198B — worse than T2 actual 178B.
  - Even if T6 were accurate at 140B, the Auto selector already picks T2 (178B < T4 502B).
  - T6 offers no new win over the existing T2 option.

---

## AC-3 — GO/NO-GO Decision

**Verdict: NO-GO**

**Aggregate:** T6 model ratio **0.5974** vs T4 baseline **0.5872** — T6 is **+1.74% WORSE** than T4.

**Root cause — T4's order-1 context Huffman already implicitly handles runs:**

When the value-code stream contains a run `[C, C, C, ...]`, T4's order-1 model sees:
- Context `prev=0` (sentinel) → symbol C: coded by context-0 table
- Context `prev=C` → symbol C: coded by context-C table. Since C appears after C with near-probability-1, context-C assigns code C a very short codeword (1-2 bits). Repeated codes cost ~1 bit each in context.

An RLE pre-pass collapses the run to 1 literal + 1 escape, but:
1. The escape symbol and side-table cost ~2B per run minimum.
2. The Huffman alphabet grows by 1 symbol → all context tables get larger.
3. The implicit context probability already achieves near-optimal coding for runs; the explicit RLE adds overhead without a matching saving.

**For files with NO runs (text, log_like):** Pure overhead — the escape tokens do nothing useful and the larger alphabet hurts.

**For files with runs (sparse_clustered):** T2 (RLE-codes alone) is the right tool — it doesn't pay T4's context-table header overhead. Composing RLE with T4 creates a hybrid worse than either pure approach.

**AC-4 is n/a.** No Rust implementation warranted.

---

## Comparison with Prior Hypotheses

| Hypothesis | Verdict | vs T4 0.587240 |
|-----------|---------|----------------|
| CUBR-0018: Axis-sorted traversal | NO-GO | destroys runs, +1186% on sparse_clustered |
| CUBR-0019: N-dim sweep (T4 N-invariance) | NO-GO | 0.0000% change across N=2..6 |
| CUBR-0021: Per-axis alphabet partitioning | NO-GO | phi spreads value-alphabet evenly |
| **CUBR-0023: RLE pre-pass + T4 (R4)** | **NO-GO** | **model +1.74% worse** |

The research converges: the T4 order-1 context Huffman is a strong absorber of the value-stream's run and local-context redundancy. Hypotheses R4 through R6 of the entropy-input series should be viewed against this backdrop.

---

## Follow-up Backlog Candidates

1. **R5 — value-as-context-key** (already in CUBR task backlog as next hypothesis): Use the raw value byte (not the code) as the Huffman context key. This gives more distinct contexts, potentially tighter per-context models for high-n_distinct files (text with 27 symbols may benefit; dense with 256 likely raw-stores regardless).

2. **Auto selector including T2 for clustered-data detection** (separate investigation): The Auto selector currently picks T4 on sparse_clustered (502B) when T2 gives 178B. A pre-encoding run-detection heuristic could route sparse_clustered to T2 automatically, saving 324B on that file and improving aggregate from 0.587240 to ~0.581. This is orthogonal to R4 and doesn't need a new ValueScheme variant — it's a selector logic improvement.

3. **CUBR-0022 (clippy hygiene)** remains in backlog, unrelated to compression ratio research.
