# H-63 — MED16 on MR/DICOM medical image (generalise H-60 across medical modalities)

**Why.** H-60 flipped the world-bench image gap on `x-ray` (16-bit grayscale) via MED16 (+9.74%, beats ppmd). The OTHER driver of the +38.4% image type-gap is `mr` (MRI, +44.1%). This extends MED16 to MR, parsing the **DICOM** header for geometry, and tests whether MED16 generalises across medical modalities.

**Method.** champion config, RT byte-exact. `mr` is **DICOM, implicit VR little-endian, no preamble** — parsed: Rows=512, Cols=512, BitsAllocated=16, Samples=1, PixelRepr=0 (unsigned), PixelData @ offset 9092, length 9 961 472 = **19 frames of 512×512 16-bit**. 16-bit MED predictor (median left/up + gradient), residual mod 65536; variants 2-byte LE vs hi/lo byte-plane split. L=min(xz-9e/PPMd/brotli-q11). Reversibility asserted. Spike `/tmp/uci-dl/spike_h60_med16.py`. Codec.rs untouched, NOT pushed.

**Corpus (real):** `mr_16bit_512w.bin` — Silesia `mr` pixel region (skip 9092-B DICOM header), 1 024 rows × 512 px × 16-bit = 1 048 576 B (2 MRI frames). sha256 `7e7af32b32d5f5e52a536…`. Geometry from the DICOM header (W=512).

## Measured (RT byte-exact). code SHA `422726d`. cubRT A/B/B2 all True.

| variant | cub bytes | self-gain | B/L (vs ppmd 226 983) |
|---|---:|---:|---:|
| A = raw 16-bit MR | 236 732 | — | 1.043 (behind ppmd) |
| **B = cub + MED16 (2-byte LE)** | **202 330** | **+14.53%** | **0.891 (beats ppmd by 10.9%)** |
| B2 = cub + MED16 (hi/lo split) | 241 377 | −1.96% | 1.063 |

Universals: xz-9e 262 308 | **PPMd 226 983** | brotli 266 844 → L=ppmd.

## Reading — GO, MED16 generalises across medical modalities

- **MED16 flips MR from behind-ppmd to leading it by 10.9%** (self-gain +14.53%, even larger than x-ray's +9.74% — MRI is spatially smoother than projection X-ray, so 2D prediction bites harder). Same predictor, same 2-byte-LE residual form (the hi/lo split loses again, −1.96%, consistent with H-60).
- **Geometry came straight from the DICOM header** (Rows/Cols/BitsAllocated = 512×512×16, 19 frames) — a standard DICOM implicit-VR-LE parse, no guessing. x-ray used a custom-header field + autocorrelation; MR uses DICOM. So **the MED16 transform is modality-invariant; only the geometry detector is per-format.**

## Verdict vector

**H-63 MED16·MR/DICOM: GO{image·MR-16bit} — MED16 generalises across medical modalities.** Two medical modalities now both flip to beating the strong universal leader with the SAME MED16 predictor: x-ray +9.74% (beats ppmd 5.5%), MR +14.53% (beats ppmd 10.9%). The image type is now transform-GO across **8-bit RGB (H-39/43/56), 16-bit grayscale x-ray (H-60), and 16-bit DICOM MR (H-63)** — the world-bench +38.4% image gap is fully addressable by shipping MED + a small geometry-detection layer (per-format: DICOM parser, custom-header field, or autocorrelation width-scan). The transform stays type/depth-gated + competitive `min(raw, MED-LE)` + id byte → byte-identical on non-image. Dedicated medical codecs (JPEG-LS 16-bit, CALIC) still lead, but vs general universals cubrim+MED16 WINS on both modalities.

**Mac orchestrator publishes the /evolution card for H-63** (status GO, image·MR-DICOM, MED16 +14.53% beats ppmd by 10.9%, generalises across medical modalities). Card-publishing Mac-side this cycle.

Codec.rs untouched (spike only). NOT pushed.
