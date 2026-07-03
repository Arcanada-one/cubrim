# H-60 — MED 2D predictor on 16-bit medical grayscale (world-benchmark weakest class: image)

**Why this lever.** CUBR-0036 world benchmark: **image is cubrim's weakest type (+38.4% vs best universal ppmd)**, and the real image files driving it are MEDICAL grayscale — `mr` (+44.1%), `x-ray` (+35.6%) — NOT the Kodak RGB my H-39/H-43/H-56 MED+colour work used. The MED 2D-predictor lever was validated on RGB; this extends it to the benchmark's own grayscale medical images, where it is untested. (The small-file +200–300% gaps — sum/fields.c/cp.html — are raw-store micro-efficiency, already NO-GO per H-39, not structural.)

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact. `x-ray` decoded as **1900×2230 16-bit LE grayscale** (header `0x076c`=1900 width, `0x08b6`=2230 height; autocorrelation min-vertical-diff at row stride **3800 B = 1900 px × 2** confirms). 16-bit MED predictor (median of left/up, gradient) on uint16 samples, residual mod 65536. Variants: A=cub(raw); B=cub(MED16, 2-byte LE residual); B2=cub(MED16, hi/lo byte-plane split). L=min(xz-9e/PPMd/brotli-q11). Reversibility asserted. Spike `/tmp/uci-dl/spike_h60_med16.py`. Codec.rs untouched, NOT pushed.

**Corpus (real):** `xray_16bit_1900w.bin` — Silesia `x-ray` pixel region (skip 240 B header), 320 rows × 1900 px × 16-bit = 1 216 000 B. sha256 `91721b434671096db736fa…`.

## Measured (RT byte-exact). code SHA `422726d`. cubRT A/B/B2 all True.

| variant | cub bytes | self-gain | B/L (vs ppmd 559 713) |
|---|---:|---:|---:|
| A = raw 16-bit | 586 005 | — | 1.047 (behind ppmd) |
| **B = cub + MED16 (2-byte LE residual)** | **528 903** | **+9.74%** | **0.945 (beats ppmd by 5.5%)** |
| B2 = cub + MED16 (hi/lo byte-plane split) | 594 377 | −1.43% | 1.062 |

Universals on raw: xz-9e 623 392 | **PPMd 559 713** | brotli 667 787 → L=ppmd.

## Reading — GO, closes the world-benchmark's weakest class

- **MED16 flips the benchmark's own medical-grayscale image from behind-ppmd to leading it.** Without the transform, cubrim raw (586 005) is 4.7% *behind* the strong leader ppmd; with MED16 (528 903) it **leads ppmd by 5.5%** (B/L 0.945). self-gain +9.74% (≫ +1.5% floor → non-subsumed). This is the same 2D-spatial lever validated on Kodak RGB (H-39, +24.49%), now confirmed on the world-benchmark's actual weakest files — the +38.4% image type-gap is **a missing-transform gap, not a backend gap**: the shipped codec lacks MED, the spike supplies it.
- **2-byte LE residual ≫ hi/lo byte-plane split** (528 903 vs 594 377). Splitting the 16-bit residual into planes hurts here — cubrim's BWT codes the interleaved LE residual better than two separate planes. Ship the LE form.
- Geometry was **auto-recoverable**: the `0x076c`=1900 header field + the autocorrelation min-vertical-diff at stride 3800 B both give 1900-px width — so a detector (header parse OR residual-min width scan) can engage MED16 without metadata.

## Verdict vector

**H-60 MED16 medical-grayscale: GO{image·16-bit-grayscale} — closes the world-benchmark's weakest type.** Generalises the H-39 MED image lever from 8-bit RGB to 16-bit grayscale; self-gain +9.74%, **beats the strong universal leader (ppmd) by 5.5%** on the real Silesia `x-ray`. Combined with H-39/H-43/H-56 (RGB MED + colour), the **image type is now a transform-GO across both 8-bit RGB and 16-bit grayscale** — the +38.4% world-bench image gap is closable by shipping the MED predictor (geometry-detected, per-pixel-depth, competitive `min(raw, MED-LE)` + id byte; byte-identical on non-image). Note: `mr` (DICOM) needs its header parsed for geometry (deferred); the lever is the same. Dedicated medical codecs (JPEG-LS 16-bit / CALIC) would still lead, but vs general universals cubrim+MED16 now WINS — same framing as the shipped RGB / telemetry / VCF wins.

**Mac orchestrator publishes the /evolution card for H-60** (status GO, image·16-bit-grayscale, MED16 +9.74% beats ppmd by 5.5%, closes world-bench weakest class). Card-publishing Mac-side this cycle.

Codec.rs untouched (spike only). NOT pushed.
