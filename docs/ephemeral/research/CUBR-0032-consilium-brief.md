# CUBR-0032 Consilium Brief — Content-Derived φ Feasibility

> Self-contained. You are one vendor on a multi-vendor design panel. Reason
> independently; do not assume other vendors' positions. Your output is a
> **design verdict**, not prose for humans.

## The codec in one paragraph

Cubrim maps a byte file into an N-dimensional cube (v1: N=2, B=256, volume
65536). Today the coordinate map φ is **purely positional**: `φ(i) = (i%256,
i//256)` where `i` is the byte's position in the file. Nothing about the
coordinate is stored — it is implied by order. The pipeline then encodes a
**distance-map** (gap-to-next-occupied along each axis) plus a **value stream**
(the bytes, entropy-coded). The current best value scheme is **T4** = order-1
per-code Huffman over the i-order value stream.

## Why positional φ is a dead end (the structural blocker)

Because φ is positional, every index `0..L-1` is occupied → the cube is fully
dense (ρ = L/65536, all gaps = 1) → the distance-map carries ~0 bytes. Measured
across CUBR-0028/0029/0030/0031: even with **zero** distance-map cost the
hypothetical aggregate (0.5867) stays above the GO threshold (0.575495). The
distance-map lever is inert under positional φ. This is Gotcha #1 (ρ=1 trap) and
Gotcha #2 (positional coordinates make internal cube axes improvement-inert).

## The CUBR-0032 question (what YOU must address)

Can a φ **derived from content** (computed from the byte/value statistics, NOT
from input position) place data sparsely in the cube (ρ < 0.3) such that
distance-map + value-stream **beats T4** (aggregate 0.587240; GO threshold
0.575495, i.e. −2%)?

The **new cost term** positional φ never had: a content-derived φ is a
permutation/map that the decoder cannot infer from order — it MUST be
transmitted. The size of that φ-map is the crux. Your design must:

1. Specify a concrete, **bijective** φ derived from content, with an explicit
   decode-side reconstruction (round-trip byte-exact is non-negotiable).
2. State exactly **what bytes encode the φ-map** and bound their size.
3. Show how sparsity (ρ<0.3) actually arises from your φ on real inputs —
   not hand-waved.

## Hard constraints (binding — violating any = NO-GO)

- **Gotcha #3 (the gate that kills most ideas):** φ is NOT free. Sorting/reordering
  the value stream by a φ-axis DESTROYS the i-order runs the value coder exploits
  (measured CUBR-0018: sparse_clustered 42 runs avg 48.8 → 1886 runs avg 1.1
  under axis-0-sort; conditional entropy worsened on every clustered file). ANY
  content-derived-φ proposal MUST pass a cheap **order-1 conditional-entropy
  probe** (H(X_t | X_{t-1}) on the resulting value stream) BEFORE implementation.
  If your φ raises conditional entropy on clustered files, it is NO-GO. Design
  your φ so it does NOT scatter runs — or argue why its sparsity gain outweighs
  the run loss, with numbers.
- **Gotcha #6:** the size model MUST charge one cost term per decoder branch,
  INCLUDING the φ-map transmission. A GO from a model that omits the φ-map cost
  is unsound.
- **Gotcha #1:** validate on a corpus with ≥1 genuinely sparse input (ρ<0.3); do
  NOT mutate the canonical 7-file baseline.
- **Gotcha #4:** BWT is the confirmed value-stream lever (separate line,
  CUBR-0028 GO −14.1%). Do not re-propose BWT — that is already won and out of
  scope here.
- **Gotcha #5:** N-sweep on the value stream is N-invariant (disproven). Do not
  propose varying N as the lever.

## Baseline numbers (T4, canonical 7-file corpus)

| file | size_bytes | t4_bytes | t4_mode |
|------|-----------:|---------:|---------|
| sparse_clustered | 2048 | 502 | cube |
| dense | 4096 | 4109 | raw |
| text | 16384 | 5705 | cube |
| log_like | 16384 | 7318 | cube |
| binary_mixed | 8192 | 8205 | raw |
| random_high | 4096 | 4109 | raw |
| sparse_small | 256 | 269 | raw |

Corpus total 51456 bytes; T4 total 30217 bytes; T4 aggregate 0.587240.
GO threshold aggregate ≤ 0.575495.

## The deterministic arbiter (runs locally, not by you)

After the panel, the orchestrator runs an order-1 conditional-entropy probe +
Gotcha-#6-complete size model on the ACTUAL corpus bytes for the most promising
candidate(s). That measurement — not any vendor's opinion — is the GO/NO-GO
arbiter. Your job is to give the probe the best-designed candidate to measure.

## Your required output (structured)

```
VENDOR: <your vendor name>
CANDIDATE φ: <name + one-paragraph precise definition: how a coordinate is
             derived from content; the bijection; the decode reconstruction>
φ-MAP WIRE COST: <what bytes encode the map; an upper bound in bytes, per-file
                 or as a formula>
SPARSITY MECHANISM: <why ρ<0.3 arises from this φ on real inputs; which corpus
                    files benefit and why>
GOTCHA #3 SELF-CHECK: <does it scatter i-order runs? predicted effect on
                      H(X_t|X_{t-1}); pass/fail your own gate with reasoning>
GOTCHA #6 BRANCH COUNT: <list decoder branches; one cost term each, incl. φ-map>
PREDICTED VERDICT: <GO / NO-GO / NEEDS-MEASUREMENT> + one-line rationale
KILL CONDITION: <the single measurement that would falsify your candidate>
```

Be concrete and quantitative. An honest NO-GO with a sharp reason is more
valuable than an optimistic GO that the probe will refute.
