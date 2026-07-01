# H-65 — BWT block-size model on TEXT (deepen H-62's highest-ROI backend lever)

**Why.** H-62 showed (via bz2 block-size proxy) that cubrim's cubrim<bzip2 gap is the 64 KB BWT block ceiling, projecting ~−12% from a u16→u32 index. This deepens it with a **direct model of cubrim's own post-BWT coder** — the order-1/order-2 conditional entropy of the *BWT output* (what cubrim's rANS+geomix approximates) — at block sizes 64 KB / 256 KB / 512 KB / 1 MB / whole-file, **calibrated against the real cubrim-64 KB champion**, on the TEXT class (its biggest weakness: 12 world-bench files lose to ppmd 17–33%).

**Method.** No codec change. For each block size B: split the file into B-byte blocks, BWT each (numpy prefix-doubling suffix array, verified on "banana"), compute the order-1 and order-2 conditional entropy of the BWT output (bytes). **Honest model (Gotcha #6):** charge a 4-byte u32 primary-index per block (the header cost the u16→u32 change adds). Calibrate: the model at 64 KB should track the real cubrim-64 KB champion; the delta at larger B is the projected gain. bzip2-9 and ppmd measured as anchors. champion config; RT byte-exact not applicable (model, not a codec run); codec.rs untouched, NOT pushed.

**Corpora (real):** Canterbury alice29 (152 KB) / lcet10 (426 KB); Silesia dickens (1 MB slice); webster (1 MB slice). Real cubrim-64 KB from H-41.

## Measured (order-2 conditional entropy of the BWT output, +4B u32 index/block; real bzip2/ppmd anchors)

| file | orig | real cub64K | bzip2-9 | ppmd | **o2 @64K** | o2 @whole | block gain 64K→whole |
|---|---:|---:|---:|---:|---:|---:|---:|
| alice29.txt | 152 089 | 49 707 | 43 202 | **38 986** | 43 038 | 42 888 | **−0.35%** (only 2.3 blocks) |
| lcet10.txt | 426 754 | 126 476 | 107 706 | **96 553** | 117 918 | 112 124 | **−4.9%** |
| dickens_1mb | 1 000 000 | 309 771 | 270 212 | **235 007** | 304 651 | 284 218 | **−6.7%** |
| webster_1mb | 1 048 576 | 258 255 | 221 791 | **193 394** | 236 630 | 233 778 | **−1.2%** |

## Findings — an honest refinement of H-62 (which was optimistic on text)

1. **Calibration: cubrim's TEXT coder ≈ bzip2 quality, NOT stronger.** real cub64K (lcet 126 476) ≈ bz2 at 100 KB (124 819, H-62) and *above* the order-2 model (117 918). So on **text**, cubrim's rANS+geomix is roughly bzip2-class — unlike code/database (H-62), where cubrim@64K *beat* bzip2@100K. H-62's "cubrim beats bzip2, so big-block beats bzip2" was a **code/database finding that does NOT transfer to text.**
2. **Block-size gain on text is a RANGE, and pinning it needs a real Rust prototype.** The order-2 model (a strong-coder lower bound) says 64K→whole = **−0.35 … −6.7%** (bigger files gain more; small/near-one-block files barely move). But since cubrim's *actual* text coder sits at bzip2 quality (above order-2), and bzip2 gains **−13.7%** from 100 KB→900 KB block (H-62), cubrim's real gain likely lands **between the order-2 −5% and the bzip2-analog −13%** — the model cannot distinguish which without measuring cubrim's own coder at a larger block. **→ A real Rust u16→u32 block prototype is required to pin the exact number; projection = −5 % to −13 % on text (~−8 % central).** The u32 index cost is negligible (idx column ≈ o2 model; 4 B × nblk).
3. **HARD CEILING — block size CANNOT make cubrim beat ppmd on text.** Even the **order-2 BWT whole-file entropy** (the strong-coder lower bound, better than cubrim will realistically reach) stays ABOVE ppmd on *every* file: alice 42 888 > 38 986; lcet 112 124 > 96 553; dickens 284 218 > 235 007; webster 233 778 > 193 394. BWT+order-2 fundamentally leaves high-order text structure that ppmd's PPM model captures. **No block size or post-BWT-coder tweak reaches ppmd on text — that needs the PPMd/CM model class (H-61).**

## Verdict vector — GO-to-PLAN (smaller than H-62 projected on text) + Rust-prototype-needed

**H-65 BWT block-size on text: GO-to-PLAN{text}, projected −5…−13% (Rust prototype needed to pin), does NOT reach ppmd.** The u16→u32 block lever is real and cheap (negligible index cost), worth doing — but **on text it is more modest than H-62's −12% and, critically, cannot close the gap to ppmd** (hard order-2 ceiling). It remains larger on code/database (H-62: cubrim's coder there IS stronger than bzip2). **Reprioritisation:** the block-size change (H-62/H-65) is a cheap intermediate (~−5-13% text, more on code/db); **the dominant TEXT lever is unambiguously H-61 (genuine PPMd)** — the only path above the order-2 ceiling to ppmd-parity. Do them stacked: u32-block first (cheap, broad), PPMd second (the text/code/database win). A real Rust block-size prototype is the next build step to pin the exact text number (the Python model brackets it −5…−13%).

**Bonus lever surfaced:** cubrim's text coder undershoots the order-2 BWT ideal by 8–13% (model < cub64K) → a **stronger post-BWT coder** (reaching order-2, e.g. a proper order-2 context model on the BWT output) is a *separate* cheap lever worth ~that gap, independent of block size — a step toward H-61 without full PPMd.

**Mac orchestrator publishes the /evolution card for H-65** (status GO-to-PLAN, block-size −5…−13% text range, Rust prototype needed to pin, hard order-2 ceiling above ppmd → PPMd/H-61 is the text lever). Card-publishing Mac-side this cycle.

Codec.rs untouched (model/analysis only). NOT pushed.
