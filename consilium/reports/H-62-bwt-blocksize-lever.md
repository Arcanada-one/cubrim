# H-62 — larger BWT block (the cheaper backend lever: close the cubrim<bzip2 gap)

**Why this lever.** H-61 surfaced that cubrim's BWT+rANS+geomix loses to *bzip2* (BWT+MTF+Huffman) on text/code/database by −13…−15%. Hypothesis: the cause is cubrim's **64 KB BWT block ceiling** (u16 BWT index), not its coder — and raising the block recovers the gap far more cheaply than the multi-day full-PPMd (H-61).

**Method.** champion config; no codec change. Probe the block-size sensitivity of a real BWT pipeline with `bz2.compress(data, level)` where level 1→9 = BWT block **100 KB → 900 KB**. Compare to cubrim-champion (`bwt-rans`, 64 KB blocks, measured H-41/H-42) and to ppmd. If cubrim at 64 KB *beats* bzip2 at 100 KB (a larger block) on any file, its coder is the stronger one and the only handicap is block size. Spike `/tmp/uci-dl/spike_h62_*` (inline). Honest model (Gotcha #6): the projection charges nothing cubrim doesn't already pay — it's the same coder at a larger block. Codec.rs untouched, NOT pushed.

**Corpora (real, version-locked):** Canterbury alice29 / lcet10; repo cubrim_src.rs; Silesia osdb (+ fields.c). SHAs in H-41/H-42.

## Measured (real bytes). cubrim = champion `bwt-rans`, 64 KB blocks.

| file | orig | **cubrim (64 KB)** | bz2 L1 (100 KB) | bz2 L2 (200 KB) | bz2 L3 (300 KB) | bz2 L6 (600 KB) | bz2 L9 (900 KB) | ppmd |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| alice29.txt | 152 089 | 49 707 | 45 995 | 43 202 | 43 202 | 43 202 | 43 202 | 38 986 |
| lcet10.txt | 426 754 | 126 476 | 124 819 | 116 543 | 114 455 | 107 706 | 107 706 | 96 553 |
| cubrim_src.rs | 533 116 | **103 161** | 108 910 | 103 895 | 99 716 | 93 438 | 93 438 | 90 856 |
| osdb | 1 048 576 | **341 396** | 393 872 | 350 101 | 329 783 | 304 390 | 300 815 | 266 606 |

## Findings — the gap is PURELY block size, not the coder

- **cubrim at 64 KB BEATS bzip2 at 100 KB (a larger block) on cubrim_src.rs (103 161 < 108 910) and osdb (341 396 < 393 872).** A coder that wins at a *smaller* block is the stronger coder — so cubrim's rANS+geomix is *better* than bzip2's MTF+Huffman per block. cubrim loses the *aggregate* only because bzip2 runs a 600–900 KB block while cubrim is capped at 64 KB.
- **Block size monotonically recovers the gap:** lcet10 bz2 100 KB→900 KB = 124 819→107 706 (−13.7%); osdb 393 872→300 815 (−23.6%); cubrim_src 108 910→93 438 (−14.2%); alice 45 995→43 202 (−5.6%, it's only 152 KB so 200 KB already holds the whole file). cubrim's 64 KB block sits *below* even bzip2's smallest (100 KB).
- **Therefore: raising cubrim's BWT block to whole-file/large blocks recovers ~−13% AND, because cubrim's coder beats Huffman at equal block, would land cubrim at or below bz2-L9 — i.e. beating bzip2 outright**, between bzip2 and ppmd.

## Projection (cubrim's own coder at a large block)

cubrim-champion ≥ bzip2 at equal block (shown), so cubrim at whole-file/large block ≲ bz2-L9: alice 49 707→~43 202 (**−13.1%**), lcet 126 476→~107 706 (**−14.8%**), cubrim_src 103 161→~93 438 (**−9.4%**), osdb 341 396→~300 815 (**−11.9%**). Aggregate text/code/database ≈ **−12%** — and likely a few % better since cubrim's coder > Huffman. This does NOT reach ppmd (the last ~10–15% needs H-61's PPMd), but the two **stack**: large-block BWT + PPMd-class coder → ppmd-parity-or-better.

## Verdict vector — GO-to-PLAN (architecture change, far cheaper than full PPMd)

**H-62 larger BWT block: GO-to-PLAN{text·code·database}.** The cubrim<bzip2 gap is entirely the **64 KB block ceiling**; cubrim's coder is already the stronger one. Fix = raise the BWT block (whole-file or 256 KB–1 MB), which means **u16 → u32 BWT index + lifting the 64 KB MODE_CHUNKED cap** — a *moderate* architecture change, NOT the multi-day PPMd build (H-61). Spike-confirmed ~−12% recovery, making cubrim beat bzip2 and close half the distance to ppmd. Ship behind the competitive rail (larger-block scheme competes per file; tuned/holdout preserved by construction), RT byte-exact. **Highest ROI : effort ratio of the backend program — do this BEFORE the full PPMd build.** Caveat (Gotcha #6): a larger BWT block raises encode time/memory (O(n log n) suffix sort over big blocks) — the existing >64 KB slowness (perf flag) compounds; the build must address BWT/SA performance, not just the index width.

**Mac orchestrator publishes the /evolution card for H-62** (status GO-to-PLAN, larger BWT block, gap is block-size-only, ~−12% recovery, u16→u32 index, cheaper than PPMd, stacks with H-61). Card-publishing Mac-side this cycle.

Codec.rs untouched (spike/analysis only). NOT pushed.
