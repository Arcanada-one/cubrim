# H-43 — color decorrelation (sub-green) before MED, image·RGB (per-type grid, new hypothesis)

**Premise.** Strengthen the proven image·continuous-tone win (H-39 MED, +24.49%). RGB channels are correlated (luminance shared across R,G,B); decorrelating colour before the 2D predictor is the standard lossless-image lever (WebP-lossless "subtract-green", JPEG-XL/FFV1 colour transforms). Hypothesis: sub-green colour decorrelation BEFORE per-channel MED reduces the residual further.

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact. Reversible **sub-green** (R'=(R−G)&255, B'=(B−G)&255, G kept — WebP lossless, exactly invertible mod 256), then per-channel MED. Cells: A=cub(raw), cub(sub-green only), cub(sub-green+MED); compared to the H-39 MED-only baseline (483 598, +24.49%). Image-only transform (engages on detected RGB raster; byte-identical / N/A on the other 5 types). Spike `/tmp/uci-dl/spike_h43_color.py`. Codec.rs untouched, NOT pushed.

**Corpus:** Kodak `kodim23_rgb.raw` 768×512×3 (PNG→raw, provenance in H-39 report).

## Measured (RT byte-exact)

| variant | cub bytes | self-gain vs A | vs strong leader (xz 629 320) |
|---|---:|---:|---:|
| A = raw | 640 443 | — | behind |
| MED only (H-39) | 483 598 | +24.49% | B/L 0.768 (beats by 30%) |
| sub-green only | 596 328 | +6.89% | 0.947 |
| **sub-green + MED** | **453 327** | **+29.22%** | **0.720 (beats by 39%)** |

(All RT byte-exact. Strong leader on this file = xz 629 320.)

## Reading

- **sub-green decorrelation STACKS on MED.** MED-only was 483 598 (+24.49%); adding sub-green first → **453 327 (+29.22%)**, an **incremental −6.26%** over MED-only — itself well above the +1.5% floor, so the colour transform is a **real additive lever, NOT subsumed** by MED or the backend. sub-green alone (+6.89%) confirms genuine inter-channel (luminance) correlation that the per-channel MED cannot remove.
- **Beats the strong universal by 39%** (B/L 0.720, up from MED-only's 0.768). cubrim+sub-green+MED leads xz/ppmd/brotli decisively on the image type.

## Verdict vector

**H-43 colour (sub-green): GO{image·RGB} — stacks on MED.** Reversible mod 256 (WebP-lossless transform), image-RGB-only (byte-identical / N/A on the other 5 types). Strengthens the H-39 image GO from +24.49% → **+29.22%** self-gain, leader-beat from 30% → 39%. Ship together with MED behind the image detector + competitive `min(raw, med, subgreen+med)` + transform-id byte.

**Pipeline now for image·RGB:** detect RGB raster geometry → sub-green colour decorrelation → per-channel MED → champion bwt-rans. Next colour lever (separate H): reversible YCoCg-R (needs 9-bit chroma handling) typically beats sub-green by a few % more; Paeth + per-row predictor selection (PNG) is an orthogonal refinement.

Codec.rs untouched (spike only). NOT pushed.
