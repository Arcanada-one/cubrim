# H-39 — 2D spatial predictor for images (per-type grid, STEP 2)

**Status:** GO(image·continuous-tone) — **flip CONFIRMED** (MED +24.49% self-gain, beats strong leader by 30%). Second methodology-validating flip after H-45/exe. NO-GO(image·bilevel) — XOR-up subsumed.

**Method.** Per-cell, champion `--value-scheme bwt-rans`, RT byte-exact. A = cubrim(raw pixels); B = cubrim(predictor-residual); L = strongest universal (min xz-9e/PPMd/brotli-q11). self-gain=(A−B)/A. GO(type) ⟺ self-gain ≥ +1.5% AND (rank-up vs L OR ≥50% of A→L gap closed). Predictors reversible (self-RT asserted). Spike script `/tmp/uci-dl/spike_h39_image.py` (+ minimal PNG decoder `/tmp/uci-dl/png_decode.py`). Codec.rs untouched, NOT pushed.

**Corpus (real, version-locked, provenance below).**
- `ptt5.bin` — Canterbury `ptt5`, CCITT bilevel fax, **1728×2376 1-bit** (513216 = 1728·2376/8, stride 216 B/row). sha256 `0ec3a75089bb52342813496b17e51377bc9eba3cb519a444d67025354841d650`. Predictor: XOR-up (row ⊕ row-above) — the bilevel analogue of MED.
- `kodim23_rgb.raw` — Kodak test image #23 (public-domain lossless benchmark), PNG→raw via minimal zlib decoder, **768×512×3 RGB** (1179648 B). Source PNG https://r0k.us/graphics/kodak/kodak/kodim23.png sha256 `e3111a2fd4da24af15d6459ef9eacfe54106b38e27b4a21821b75c3f5d2d5baf`. Predictor: JPEG-LS MED (median of left/up, gradient) per channel.

## Measured (RT byte-exact)

| file | predictor | A=cub raw | B=cub resid | self-gain | xz | ppmd | brotli | L | B/L | cell |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| ptt5 (bilevel 1728×2376) | XOR-up | 44 825 | 45 814 | **−2.21%** | 39 860 | 49 183 | 40 939 | xz | 1.149 | **NO-GO** (subsumed) |
| kodim23 (RGB 768×512) | MED | 640 443 | **483 598** | **+24.49%** | 629 320 | 654 328 | 634 857 | xz | **0.768** | **GO** |

## Reading

- **kodim23 = GO(image·continuous-tone), large and clean.** MED self-gain **+24.49%** (≫ +1.5% floor → strongly NOT subsumed — exactly the 2D-spatial structure invisible to a 1-D byte pipeline). And B (483 598) **beats the strongest universal** xz (629 320) by 30% (vs PPMd 654 328, brotli 634 857). Without MED, cubrim raw (640 443) was *behind* every universal (none of xz/ppmd/brotli has a 2D model either); MED gives cubrim the spatial model and it leaps ahead by 24–26%. Full rank-up, >100% of the A→L gap closed. RT byte-exact.
- **ptt5 = NO-GO (subsumed).** XOR-up makes cubrim *worse* (−2.21%): cubrim's BWT/LZ already captures the vertical run-correlation of fax data, so explicit row-XOR only adds noise — a clean Gotcha #11 subsumption on bilevel. (cubrim raw 44 825 is itself behind xz 39 860 here; bilevel fax favours run-coders.) Bilevel is not the MED profile.

## Verdict vector

**H-39 2D-predictor: GO{image·continuous-tone} · NO-GO{image·bilevel}.** MED is a real, large, non-subsumed structural win on continuous-tone raster (+24.49% self-gain, beats the strong universal leader by 30%), and is cleanly **type-gated** (engages only on detected raster with known geometry; byte-identical elsewhere) → SHIPS for the continuous-tone image type. Bilevel is subsumed and excluded.

**Honest scope (domain-codec context).** The gate here is vs strong *universal* archivers (xz/ppmd/brotli), per the methodology — and cubrim+MED wins that decisively. MED is the same predictor PNG/JPEG-LS use, so cubrim+MED ≈ a basic lossless image codec; dedicated image codecs (JPEG-LS / FFV1 / JPEG-XL modular) would still lead. For a *general archiver beating general universals* on the image type, this is a genuine GO — the same framing as the shipped telemetry/VCF wins.

**Methodology validation: 2nd PASS.** Image continuous-tone flips false-NO-GO→GO, confirming the grid surfaces type-specific wins a global verdict buries (here the bilevel −2.21% and the +24.49% continuous-tone would have averaged into a muddy/NO-GO global verdict).

## Productionization notes (pre-Rust, when greenlit)
1. Geometry detection: raster needs (W, H, bpp). For headered formats (PNG/BMP/PNM/TIFF) parse the header; for raw, autodetect stride via min-residual-entropy scan over candidate widths.
2. Per-channel MED on interleaved RGB(A); optionally add Paeth and pick competitively `min(raw, med, paeth)` + predictor-id byte → regression-proof, byte-identical on non-raster.
3. Color transform (reversible RGB→YCoCg-R) before MED is the standard next lever (decorrelates channels) — separate hypothesis.

Codec.rs untouched (spike only). NOT pushed.
