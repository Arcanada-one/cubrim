# H-45 — Context-Tree Weighting (CTW) as a table-free adaptive backend

**Status:** PLANNED (research candidate, round-3 ladder). No Cubrim measurement yet — numbers below are literature estimates.

**Class targeted:** text / source code + all cube-mode files (entropy backend, not a transform).

## Hypothesis

Replacing or augmenting geomix's fixed geometric o0/o1/o2 mix with a Context-Tree Weighting model on the BWT'd value stream reduces bits-per-symbol, because CTW is a principled Bayesian mixture over ALL context depths 0..D and provably approaches the best-order redundancy without manual order selection.

## Why it might help — and why this is NOT the CLOSED order-2 branch

The CLOSED order-2 fallback chains (Gotcha #6; `closed-branches.md` § order-2) died on **transmitted static-table cost**. CTW transmits **NO table** — it is fully adaptive; the decoder rebuilds the identical context tree online as it decodes. So the table-cost failure mode that killed order-2 does not apply here. CTW weights all depths simultaneously (no fallback chain, no order-selection) and measured ~0.09 bpb better than PPMd on the Calgary corpus.

## Expected lever (estimate — NOT a Cubrim measurement)

- ~0.09 bpb over PPMd on Calgary (CTW literature) → a few % on BWT'd text streams where geomix's fixed mix is suboptimal.

## Mandatory gate (Gotcha #9 — learning cost, NOT table cost)

CTW still pays an **online learning** cost. Over a 256-symbol byte alphabet on a 64 KB block, the binary-decomposed CTW (8 bit-trees/symbol) MUST be simulated with a REAL adaptive coder (not ideal entropy) and checked against the cell-count ÷ stream-length sanity bound (Gotcha #9 — ~1 obs/cell cannot learn).

1. Probe: binary CTW vs geomix bpb on the REAL BWT'd `text` / `binary_mixed` value streams.
2. If learning cost > geomix gain on 64 KB → NO-GO at block scale (same scale caveat as H-39's table amortization).
3. Competitive / self-disabling so no regression risk.

## Refs

- Context-Tree Weighting, Willems / Shtarkov / Tjalkens, IEEE Trans. Information Theory 1995 — https://en.wikipedia.org/wiki/Context_tree_weighting
- Implementing CTW for Text Compression — https://ieeexplore.ieee.org/abstract/document/838152/

## Measured

_Pending — to be filled by the implementing session with cubrim vs gzip-9 vs zstd-19, RT result, and code SHA._

## Verdict

_Pending._
