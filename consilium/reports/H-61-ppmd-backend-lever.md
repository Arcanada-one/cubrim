# H-61 — PPMd-class / context-mixing backend (the shared lever of text/code/database)

**Why this lever.** Three NO-GO-transform types (text H-41, code & database H-42) all point to the SAME orthogonal lever: a stronger entropy backend. cubrim trails the genuine-PPMd reference by ~1.13–1.31× on these types with NO transform available to close it. This spike quantifies the lever's ceiling and realizable projection, per Gotcha #6 (charge the real coder, not an ideal).

**Method.** champion config; no codec change. For each real text/code/database file: cubrim-champion bytes (measured H-41/H-42, `bwt-rans`) vs **bzip2** (BWT+MTF+Huffman, 900 KB block) vs **PPMd** (7z `-m0=PPMd`, genuine PPM with escape+SEE) vs the **order-2 / order-3 static conditional-entropy ceiling** (ideal bytes a perfect order-N coder reaches). bpc = bits/byte. Spike `/tmp/uci-dl/spike_h61_backend.py`. Codec.rs untouched, NOT pushed.

**Corpora (real, version-locked):** Canterbury alice29 / lcet10 / fields.c; repo cubrim_src.rs; Silesia sao (with the H-40 SoA transform applied) + osdb. (SHAs in H-41/H-42/H-40 reports.)

## Measured (real bytes; cubrim = champion `bwt-rans`)

| file | orig | cubrim | bzip2 | PPMd | H2-ideal | H3-ideal | cub/ppmd | ppmd bpc | cub bpc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| alice29.txt (text) | 152 089 | 49 707 | 43 202 | **38 986** | 47 246 | 33 782 | 1.275 | 2.051 | 2.615 |
| lcet10.txt (text) | 426 754 | 126 476 | 107 706 | **96 553** | 139 350 | 98 063 | 1.310 | 1.810 | 2.371 |
| fields.c (code) | 11 150 | 3 408 | 3 039 | **2 761** | 2 049 | 1 208 | 1.234 | 1.981 | 2.445 |
| cubrim_src.rs (code) | 533 116 | 103 161 | 93 438 | **90 856** | 144 740 | 92 572 | 1.135 | 1.363 | 1.548 |
| osdb (database) | 1 048 576 | 341 396 | 300 815 | **266 606** | 284 361 | 114 184 | 1.281 | 2.034 | 2.605 |
| sao (binary, SoA-transformed) | 700 000 | **459 034** | 479 996 | 464 306 | 233 710 | 101 243 | 0.989 | 5.306 | 5.246 |

## Findings (real numbers)

1. **The backend deficit is larger than "vs PPMd" — cubrim loses to bzip2 too.** On every text/code/database file cubrim's BWT+rANS+geomix is *worse than bzip2's* BWT+MTF+Huffman (alice 49 707 vs 43 202; lcet 126 476 vs 107 706; osdb 341 396 vs 300 815) — −13% to −15% just to reach bzip2. A BWT pipeline with a *worse* entropy stage than 1990s Huffman points to two fixable causes: **(a) cubrim's 64 KB BWT block vs bzip2's 900 KB** (smaller block → less context captured; lcet's many 64 KB blocks vs one bzip2 block), and **(b) the geomix post-BWT coder underperforming**. This is a CHEAPER intermediate win than full PPMd.
2. **PPMd realises near the order-3 ceiling; cubrim is far above it.** alice H3-ideal 33 782 < ppmd 38 986 ≪ cubrim 49 707 (cub bpc 2.615 vs ppmd 2.051 — a 27% backend gap). The high-order context structure is real and large; PPMd's escape+SEE+order-blending captures it, cubrim's order-0/1/2 geomix does not.
3. **Where a transform already fires, the backend is NOT the bottleneck.** sao (with the H-40 SoA byte-plane transform) → cubrim 459 034 ≈ PPMd 464 306 (cub/ppmd 0.989, cubrim slightly ahead). So the backend deficit is specific to the **non-transform-helped streams** (raw text/code/database, and the LZ literal/exe residues where xz/LZMA2 beat cubrim, H-57).

## Projection (integrating a PPMd-class backend behind the competitive rail)

Per-file, cubrim → ~PPMd ratio: alice 49 707→~38 986 (**−21.6%**), lcet 126 476→~96 553 (**−23.7%**), osdb 341 396→~266 606 (**−21.9%**), code .rs 103 161→~90 856 (**−11.9%**). Aggregate text/code/database ≈ **−20%**, moving cubrim from rank ~7–8 to ~2–3 on those types, AND closing the exe/binary residual where LZMA2 leads (H-57). It lifts the whole leaderboard, exactly as the three NO-GO grids predicted.

## Verdict vector — GO-to-PLAN (multi-day Rust, not a one-spike ship)

**H-61 backend: GO-to-PLAN{text·code·database + exe/binary residual}.** The lever is real and large (measured ~1.27–1.31× to PPMd; ~−20% projected) and is the single highest-ROI remaining work. But it is **NOT a spike-shippable change**: a genuine PPMd (order-4..6 + escape C/D + SEE + order blending + deterministic range coder) is a multi-day Rust build — a *simple* adaptive order-N model is a measured NO-GO (Gotcha #9 learning-cost wall; CUBR-BACKEND-SPIKE: naive o1/o2/o3 = 251K/323K/367K, WORSE than bwt-rans). **Operator decision needed on the build.** New value-scheme `ppmd` (byte 13) behind competitive `min()` → tuned/holdout preserved by construction, RT byte-exact, applies to the value stream + MODE_BINFLOAT/MODE_VCF sub-blobs.

**Cheaper intermediate lever surfaced (separate hypothesis):** the cubrim-loses-to-bzip2 finding means **(a) a larger BWT block (>64 KB) and (b) a stronger post-BWT coder** could recover ~−13% (the bzip2 gap) at far lower cost than full PPMd — worth a dedicated spike before committing the multi-day PPMd build.

**Mac orchestrator publishes the /evolution card for H-61** (status GO-to-PLAN, backend lever, measured ~1.27–1.31× to PPMd, projected −20%, multi-day build; bonus: cubrim<bzip2 → cheaper block-size lever). Card-publishing Mac-side this cycle.

Codec.rs untouched (spike/analysis only). NOT pushed.
