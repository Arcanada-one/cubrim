# H-56 — YCoCg-R (reversible, 9-bit chroma) colour transform before MED, image·RGB

**Premise.** YCoCg-R is the JPEG-XL/H.264 reversible colour transform; it decorrelates RGB more completely than WebP sub-green (H-43), but its chroma channels (Co, Cg) need 9 bits each (range [-255,255]). Hypothesis: YCoCg-R + MED beats the shipped sub-green+MED (453 327, +29.22%) on image·RGB despite the 9-bit chroma storage cost.

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact. Reversible YCoCg-R (`Co=R−B; t=B+(Co>>1); Cg=G−t; Y=t+(Cg>>1)`), planar layout (Y/Co/Cg separate 2D planes), **per-plane MED**, 9-bit chroma serialised honestly as `MED(Y) ++ MED(Co_lo) ++ MED(Cg_lo) ++ packbits(Co_hi) ++ packbits(Cg_hi)` — the near-constant hi-bit bitplanes are appended raw and **charged** (Gotcha #7). Reversibility asserted before measuring. Image-RGB-only (byte-identical elsewhere). Spike `/tmp/uci-dl/spike_h56_ycocg.py`. Codec.rs untouched, NOT pushed.

**Corpus:** Kodak `kodim23_rgb.raw` 768×512×3 (provenance in H-39 report).

## Measured (RT byte-exact)

| variant | cub bytes | self-gain vs A | note |
|---|---:|---:|---|
| A = raw | 640 443 | — | |
| MED only (H-39) | 483 598 | +24.49% | |
| sub-green + MED (H-43, shipped) | 453 327 | +29.22% | current image champion |
| **YCoCg-R + MED (H-56)** | **446 338** | **+30.31%** | blob +8.3% pre-comp (9-bit chroma charged) |

Pre-compression blob = 1 277 952 B (+8.3% over raw, from the 9-bit Co/Cg hi-bit planes — which compress to near-zero as expected). Strong leader on this file = xz 629 320 → **B/L 0.709 (beats leader by 41%)**. **code SHA `422726d`** (codec untouched; spike measured on the shipped champion binary).

## Reading

- **YCoCg-R + MED = the best image·RGB result so far: 446 338 (+30.31% self-gain), beats the strong universal leader by 41%.** RT byte-exact; the +8.3% pre-compression expansion from 9-bit chroma is fully recovered (the hi-bit planes are near-constant → compress away), so the richer decorrelation nets out ahead.
- **But the incremental over the shipped sub-green+MED is marginal:** 453 327 → 446 338 = **−1.54%** (self-gain +29.22% → +30.31%, +1.09 pp). That sits right at the +1.5% non-subsumption floor — a *real but small* edge for a *more complex* transform (9-bit chroma serialisation + per-plane MED vs sub-green's trivial mod-256 subtract + interleaved MED).

## Verdict vector

**H-56 YCoCg-R: GO{image·RGB} — best-in-class, but marginal over sub-green.** It is the strongest measured image·RGB pipeline (+30.31%, leader-beat 41%) and is non-subsumed vs the no-transform baseline. The **incremental 1.54% over the simpler sub-green (H-43) is at the noise floor** — so this is a GO with an honest engineering caveat: adopt YCoCg-R for the extra ~1.5% only if the 9-bit-chroma handling complexity is acceptable; otherwise sub-green (H-43) captures ~95% of the colour-decorrelation benefit at far lower complexity. Recommended ship: YCoCg-R as the image·RGB colour stage behind competitive `min(raw, sub-green+MED, YCoCg-R+MED)` + transform-id byte (so the encoder picks whichever wins per image; both are type-gated to RGB raster, byte-identical elsewhere).

**Orchestration note (Mac-side this cycle):** the Mac orchestrator must add the `/evolution` card for H-56 (title, mechanism, measured +30.31% / leader-beat 41% / incremental +1.54% over sub-green, status=GO-marginal) and run the deploy — **card-publishing is Mac-side this cycle**, not done here.

Codec.rs untouched (spike only). NOT pushed.
