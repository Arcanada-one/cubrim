# Cubrim Autonomous Research Iteration Brief

**Iteration ID:** {{ITERATION_ID}}
**Date:** {{DATE}}
**Vendor slot:** {{VENDOR_SLOT}}  (Vendor A / Vendor B / Vendor C)

---

## Your Role

You are **{{VENDOR_SLOT}}** in a three-vendor compression-research panel.
Your task is to propose ONE novel hypothesis for improving the Cubrim
lossless archiver beyond its current best. Proposals are independent —
you do not see other vendors' responses until the judge scores them.

Read the full brief carefully. The Gotcha list and closed-branch ledger
are hard constraints — proposals that violate them will be auto-rejected.

---

## Codec in One Paragraph

Cubrim maps a byte stream of length L to an N-dimensional cube of
edge-bound B (currently N=2, B=256 for most inputs). Each distinct
byte value gets a code in [0, n_distinct); the resulting value-code
sequence is processed by a ValueScheme. The current best ValueScheme
is **BWT-Entropy**: apply Burrows-Wheeler Transform (sorted by
context, LF-mapping + one primary_index integer) then order-1
conditional Huffman on the BWT output. The bitstream is:
header (magic + config) + distance-map (per-axis RLE of gaps to next
populated cube position) + value-codes (BWT+Huffman compressed). A
competitive per-file selector writes `min(BWT, T4)` + 1 scheme byte
per file — structurally regression-proof.

---

## Live Baseline Numbers

| Metric | Value |
|--------|-------|
| Scheme | {{CURRENT_SCHEME}} |
| Aggregate ratio (compressed/raw, 7-file corpus subset) | **{{CURRENT_AGGREGATE}}** |
| vs T4 (order-1 Huffman, no BWT) | {{DELTA_VS_T4}} |
| vs gzip -9 (10-file corpus) | {{VS_GZIP}} |
| vs xz -9 (10-file corpus) | {{VS_XZ}} |
| Win target | aggregate ≤ {{WIN_TARGET_GZIP}} (beat gzip) |
| Code SHA | {{CODE_SHA}} |
| Corpus manifest SHA256 | {{CORPUS_MANIFEST_SHA256}} |

The BWT scheme is strongest on structured text/log files (run locality
in value-code space → BWT benefit) and neutral on high-entropy/raw files
(T4 wins per competitive selector).

---

## Corpus (frozen — do not suggest adding files)

10 files, 117032 raw bytes total. Key statistics from the frozen manifest:

| File | Size | rho | Notes |
|------|------|-----|-------|
| sparse_clustered | 2048 B | 0.031 | BWT ≡ T4 (short runs) |
| dense | 4096 B | 0.063 | Raw mode (cube overhead) |
| text | 16384 B | 0.250 | BWT wins (−2122 B vs T4) |
| log_like | 16384 B | 0.250 | BWT wins (−2140 B vs T4) |
| binary_mixed | 8192 B | 0.125 | T4 mode |
| random_high | 4096 B | 0.063 | T4 mode (near-random) |
| sparse_small | 256 B | 0.004 | T4 mode |
| both_sparse_16 | 16 B | 0.000 | Overhead dominates |
| both_sparse_24 | 24 B | 0.000 | Overhead dominates |
| block_bound_runs | 65536 B | 1.000 | BWT shines (9011 vs T4 24624) |

---

## Gotcha Checklist (Mandatory — self-assess before writing your proposal)

Before writing your proposal, verify it does NOT fall into these traps:

1. **rho=1 corpus trap.** A corpus with all gaps=1 (rho=1) tests only
   value-stream packing, not the cube mechanism. Distance-map ideas need
   rho < 0.3 inputs to validate the gap principle.

2. **Positional-phi inertness.** Sweeping N or B does not move the T4
   ratio (codec produces i-order value stream regardless of N). If your
   idea targets N/B tuning for T4 improvement — it will not work (Gotcha #5).

3. **Phi not locality-preserving.** Sorting the value stream by phi
   coordinate destroys runs (axis-0-sort destroyed 1886 runs vs 42 i-order).
   Any axis-traversal or coordinate-reordering idea MUST pass an order-1
   conditional-entropy check before implementation.

4. **BWT is the confirmed lever.** BWT of i-order value-code stream +
   order-1 Huffman = current best (−14.1% vs T4). New ideas in this space
   must beat 0.504412 aggregate on the frozen corpus.

5. **N-invariance of T4 value stream.** T4 value stream is byte-exact
   identical across N=2..6 (structural proof). N-sweep targeting T4 = no-op.

6. **Full-branch size model.** Multi-fallback schemes MUST charge one cost
   term per decoder branch. A model with fewer terms than branches is unsound —
   a GO from such a model will be rejected by the arbiter.

7. **phi-map-as-branch.** Any phi that stores/transmits a permutation map
   must charge the map cost as a decoder branch. Information conservation:
   map cost ≥ disorder removed from value stream → cannot net-win on the
   compressed output. This closes ALL coordinate-storing phi variants.

---

## Closed-Branch Ledger (auto-reject if your proposal matches)

The following directions are proven exhausted. A proposal in any of these
categories will be auto-rejected without implementation:

{{CLOSED_BRANCHES_SUMMARY}}

---

## Required Structured Output Format

Your response MUST include a **PROPOSAL** block in this exact format.
Do not add extra fields; do not omit any field.

```
PROPOSAL:
  candidate_name: <short identifier, e.g. "PPM-order2-value-stream">
  mechanism_one_sentence: <what it does and why it reduces H(compressed)>
  sparsity_mechanism: <how it interacts with the cube's distance-map, or "none — value-stream only">
  decoder_branches:
    - <branch 1 name and byte cost estimate>
    - <branch 2 name and byte cost estimate>
    ...
  gotcha3_self_check: <does this idea sort/reorder by phi-coordinate? yes/no — if yes, auto-NO-GO>
  gotcha6_branch_count: <count decoder branches above; cost_terms must be >= this count>
  gotcha7_phi_map_check: <does this transmit a permutation map? yes/no — if yes, auto-NO-GO>
  closed_branch_check: <does this match any closed branch above? yes/no — if yes, auto-NO-GO>
  predicted_verdict: <GO / NO-GO and brief rationale>
  kill_condition: <what measurement result would prove this NO-GO>
  estimated_aggregate_improvement: <rough delta vs 0.504412, e.g. "-0.02 to -0.05">
```

---

## Constraints

- Proposals are voice-bearing — this is YOUR model's compression insight.
- Round-trip correctness is non-negotiable (no lossy compression).
- Free-tier rate limits apply; keep responses concise.
- Real numbers only — no estimated ratios without measurement.
- Only one proposal per vendor per iteration.
