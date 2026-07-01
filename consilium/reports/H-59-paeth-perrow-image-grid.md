# H-59 — PNG-style per-row adaptive filter selection (Paeth et al.), image·RGB

**Premise.** The shipped image·RGB pipeline uses a single fixed 2D predictor (MED), optionally after a colour transform (sub-green H-43 / YCoCg-R H-56). PNG instead picks the best of {none, sub, up, avg, Paeth} **per scanline**, adapting to row-varying content. Hypothesis: per-row adaptive filter selection beats the fixed MED predictor (incremental vs YCoCg-R+MED 446 338 / sub-green+MED 453 327).

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact. Per scanline pick the filter minimising the PNG sum-of-absolute-signed-residual heuristic; emit `filter_byte ++ residuals` per row. Reversible (decoder applies the per-row inverse; asserted). Variants: PNG on raw RGB; PNG after sub-green colour transform. Spike `/tmp/uci-dl/spike_h59_png.py`. Codec.rs untouched, NOT pushed.

**Corpus:** Kodak `kodim23_rgb.raw` 768×512×3 (provenance in H-39 report).

## Measured (RT byte-exact). code SHA `422726d`.

| variant | cub bytes | self-gain vs A | note |
|---|---:|---:|---|
| A = raw | 640 443 | — | |
| MED only (H-39) | 483 598 | +24.49% | |
| sub-green + MED (H-43) | 453 327 | +29.22% | |
| YCoCg-R + MED (H-56, best shipped) | 446 338 | +30.31% | |
| **PNG per-row (H-59)** | 479 939 | +25.06% | filters: avg×267, up×134, Paeth×109, sub×1, none×1 |
| **sub-green + PNG per-row** | 454 201 | +29.08% | |

All RT byte-exact. Strong universal leader on this file = xz 629 320.

## Reading — NO-GO

- **PNG per-row alone (+25.06%) ≈ MED-only (+24.49%)** — a marginal +0.76% edge, i.e. essentially the same. Per-row adaptive selection of the simple PNG filters lands right where the single fixed MED predictor does (MED ≈ the median-of-{left,up,gradient} is already close to the per-row-optimal of {sub,up,avg,Paeth}).
- **After colour decorrelation, MED WINS:** sub-green+PNG (454 201, +29.08%) is **0.19% WORSE** than sub-green+MED (453 327, +29.22%). And the best shipped, **YCoCg-R+MED (446 338, +30.31%), beats every PNG variant.**
- The per-row filter histogram (avg 267 / up 134 / Paeth 109 of 512 rows) shows real adaptation, yet the net result does not exceed a single MED pass — confirming MED already captures what per-row filter switching offers on this content.

## Verdict vector

**H-59 PNG per-row selection: NO-GO{image·RGB} — competitive with, but does not beat, MED.** Per-row adaptive selection of {none,sub,up,avg,Paeth} matches MED-only (±0.8%) and loses to the shipped colour+MED pipelines (sub-green+MED, YCoCg-R+MED). It adds per-row state + a filter byte/row for no net gain. The shipped image·RGB champion stays **YCoCg-R+MED (+30.31%)** / sub-green+MED (+29.22%). No change to ship. (A 6th per-row option = MED itself would always be picked → degenerates to MED; no headroom.)

**Mac orchestrator publishes the /evolution card for H-59** (status NO-GO, lesson: per-row PNG filters ≈ MED, single strong 2D predictor already optimal). Card-publishing Mac-side this cycle.

Codec.rs untouched (spike only). NOT pushed.
