---
artifact: weakness-map
task: CUBR-0001
created: 2026-07-01
source_data: consilium/cubr-weakness-data.txt (CUBR-0034 world-bench, code_sha 6f76826)
---

# CUBR — World-Benchmark Weakness Map

> **Strategic frame (operator).** Cubrim is NOT one algorithm — it is an **adaptive
> ensemble**. The archiver detects each file's **type** (text / code / exe / image /
> binary / database), **size-bucket** (tiny <64 KB / small / large), and
> **characteristics** (sparsity ρ, structure, entropy), then dispatches the optimal
> Cubrim branch per file. The goal state: **beat every rival on every benchmark file**
> by routing each file to the branch that owns its class.
>
> **Where we are (CUBR-0034).** In the SHIPPED default codec Cubrim loses on **all 24**
> world-bench files. This is NOT a claim that the algorithm can't win — it is that the
> H-39..H-63 **type-gated transforms are validated spikes not yet in `codec.rs`**, and
> the shared entropy backend (BWT+geomix/rANS, ~5/8 general) is one PPMd-class upgrade
> behind on the classes that have no structural transform. This map decomposes every
> loss along one explanatory axis and turns each into a consilium question.

**Loss legend (axis):**

- **`MISSING-TRANSFORM`** — a validated GO spike exists (cite H-NN) but is not shipped;
  the loss is an integration gap, not a research gap. **The fastest wins.**
- **`BACKEND-CEILING`** — no structural transform exists for the class (Gotcha #11 /
  H-41 / H-42); the gap is the entropy backend's strength. Fixed by H-61 (PPMd-class)
  and/or H-62 (larger BWT block).
- **`TINY-FILE / CUBE-MODE`** — file <64 KB, dispatched to CUBE mode, ranks **last**;
  H-39 diagnosed this as a micro-efficiency ceiling but the CUBE-mode rank-7 result is
  worse than gzip — a **dispatcher** problem on top of the backend problem.
- **`AT-FLOOR`** — Cubrim already ≈ leader (edge case); little slack.

---

## Per-file weakness table (all 24)

| # | file | type | orig | mode | rank | cub | loses to | gap% | axis | next lever (cite) |
|---|------|------|------|------|------|-----|----------|------|------|-------------------|
| 1 | dickens | text | 10.2 MB | LZ | 6 | 0.2903 | ppmd 0.2253 | 28.8 | BACKEND-CEILING | H-61 PPMd + H-62 block |
| 2 | mozilla | exe | 51 MB | LZ | 4 | 0.3066 | xz 0.2611 | 17.4 | MISSING-TRANSFORM (partial) + BACKEND | H-45 BCJ (dense-.text spans) + H-61 |
| 3 | mr | image | 9.97 MB | CHUNKED | 3 | 0.254 | ppmd 0.2308 | 10.1 | **MISSING-TRANSFORM** | **H-63 MED16 (GO, beats ppmd +10.9%)** |
| 4 | nci | database | 33.5 MB | LZ | 3 | 0.0478 | xz 0.0432 | 10.7 | BACKEND-CEILING | H-61 + H-62 |
| 5 | ooffice | exe | 6.15 MB | LZ | 5 | 0.4355 | xz 0.3945 | 10.4 | **MISSING-TRANSFORM** | **H-45 BCJ x86 (GO, beats leader on .text)** |
| 6 | osdb | database | 10 MB | LZ | 6 | 0.3093 | ppmd 0.2366 | 30.7 | BACKEND-CEILING | H-61 (measured −21.9% proj) + H-62 |
| 7 | reymont | text | 6.6 MB | LZ | 6 | 0.2136 | ppmd 0.1722 | 24.0 | BACKEND-CEILING | H-61 + H-62 |
| 8 | samba | code | 21.6 MB | LZ | 4 | 0.1934 | xz 0.1731 | 11.8 | BACKEND-CEILING | H-61 / H-62 (H-42 code=no-transform) |
| 9 | sao | binary | 7.25 MB | CHUNKED | 5 | 0.6847 | xz 0.6103 | 12.2 | **MISSING-TRANSFORM** + BACKEND | **H-40-byteplane SoA W=28 (GO +5.33%)**; residual=backend |
| 10 | webster | text | 41.5 MB | LZ | 6 | 0.2105 | ppmd 0.1578 | 33.4 | BACKEND-CEILING | H-61 + H-62 (worst text gap) |
| 11 | x-ray | image | 8.47 MB | CHUNKED | 3 | 0.5094 | ppmd 0.4545 | 12.1 | **MISSING-TRANSFORM** | **H-60 MED16 (GO, beats ppmd +5.5%)** |
| 12 | xml | text | 5.35 MB | LZ | 5 | 0.0907 | brotli 0.0805 | 12.6 | BACKEND-CEILING | H-61 (order-2 literal / structured markup) |
| 13 | enwik8 | text | 100 MB | LZ | 5 | 0.2622 | ppmd 0.224 | 17.0 | BACKEND-CEILING | H-61 + H-62 |
| 14 | alice29.txt | text | 152 KB | CHUNKED | 6 | 0.3268 | ppmd 0.2563 | 27.5 | BACKEND-CEILING (block-cap) | **H-62 (64 KB cap; proj −13.1%)** + H-61 |
| 15 | asyoulik.txt | text | 125 KB | CHUNKED | 4 | 0.3481 | ppmd 0.2903 | 19.9 | BACKEND-CEILING (block-cap) | H-62 + H-61 |
| 16 | cp.html | text | 24.6 KB | CUBE | 7 | 0.3265 | ppmd 0.272 | 20.0 | **TINY-FILE / CUBE-MODE** | Cluster-A dispatcher Q + H-61 |
| 17 | fields.c | code | 11.15 KB | CUBE | 7 | 0.3056 | brotli 0.2437 | 25.4 | **TINY-FILE / CUBE-MODE** | Cluster-A dispatcher Q |
| 18 | grammar.lsp | code | 3.72 KB | CUBE | 7 | 0.3873 | brotli 0.3023 | 28.1 | **TINY-FILE / CUBE-MODE** | Cluster-A dispatcher Q |
| 19 | kennedy.xls | binary | 1.03 MB | LZ | 2 | 0.0513 | xz 0.0504 | 1.9 | **AT-FLOOR** | H-40-byteplane NO-GO (BIFF var-record); micro only |
| 20 | lcet10.txt | text | 426 KB | LZ | 6 | 0.2964 | ppmd 0.2262 | 31.0 | BACKEND-CEILING | H-61 (proj −23.7%) + H-62 |
| 21 | plrabn12.txt | text | 481 KB | CHUNKED | 6 | 0.3636 | ppmd 0.275 | 32.2 | BACKEND-CEILING (block-cap) | H-62 + H-61 |
| 22 | ptt5 | image | 513 KB | LZ | 4 | 0.0873 | xz 0.0777 | 12.5 | BACKEND-CEILING | H-39 bilevel NO-GO (MED −2.21%, subsumed); backend only |
| 23 | sum | binary | 38.2 KB | CUBE | 7 | 0.3458 | xz 0.2484 | 39.2 | **TINY-FILE / CUBE-MODE** | Cluster-A dispatcher Q (worst gap) |
| 24 | xargs.1 | text | 4.23 KB | CUBE | 7 | 0.453 | brotli 0.3463 | 30.8 | **TINY-FILE / CUBE-MODE** | Cluster-A dispatcher Q |

**Aggregate-by-type (from data):** binary 12.1% · code 11.8% · database 10.0% · exe
16.3% · image 11.2% · **text 21.1%** (worst class). Leader is `xz` on 4/6 type-aggregates,
`ppmd` on text+image.

---

## Weakness clusters

### Cluster A — Tiny-file CUBE-mode penalty (5 files, all rank 7 / last place)

**Files:** cp.html (24.6 KB, 20.0%), fields.c (11 KB, 25.4%), grammar.lsp (3.7 KB, 28.1%),
sum (38 KB, 39.2%), xargs.1 (4.2 KB, 30.8%).

**Signature.** Every file <64 KB is dispatched to **CUBE mode** and lands **dead last
(rank 7/8)** — behind gzip on several. This is the ensemble's single ugliest optics
result. H-39 (`H-39-small-file-class.md`) diagnosed the *ratio* gap as a
micro-efficiency ceiling (repcode-LZ-parse + brotli order-2-literal + dictionary
cold-start, all NO-GO on ≤64 KB). But H-39 measured the LZ/columnar rails — it did NOT
ask whether **CUBE mode itself is actively worse than falling back to the LZ/geomix rail**
on tiny files. The rank-7 placement suggests the dispatcher is choosing CUBE where a
plain order-1/order-2 small-block path would already beat gzip.

**Consilium question (A):** *Should the size-detector route files <64 KB away from CUBE
mode entirely to a dedicated small-block path, and what is that path?* **Predicted lever:**
a tiny-file mode = competitive `min(CUBE, LZ-geomix, order-2-adaptive-small-block)` with
the CUBE branch demoted, targeting **≥ brotli/gzip parity** (not xz — H-39 shows the
last ~15 % is micro-efficiency). Even parity flips 5 files off rank 7. Cheap: no new
transform, a dispatch-policy + one small-block coder. Charge the CUBE-vs-alt selector
byte (already how competitive min works).

### Cluster B — Text / code / database backend gap (11 files, the mass of the loss)

**Files:** dickens, reymont, webster, xml, enwik8, lcet10 (text·LZ); alice29, asyoulik,
plrabn12 (text·CHUNKED); samba (code·LZ); nci, osdb (database·LZ). Gaps 10.7–33.4 %,
and this is the **21.1 % text aggregate** — the largest single lever in the whole bench.

**Signature.** No reversible structural transform exists for these classes — redundancy
is high-order context, a **backend property** (Gotcha #11; H-41 text NO-GO(transform);
H-42 code+database NO-GO(transform)). Two measured sub-causes:

1. **Coder strength.** H-61 (`H-61-ppmd-backend-lever.md`): cubrim loses to *bzip2 too*
   on all text/code/db (−13..−15 %); cub/ppmd = 1.275 (alice29), 1.310 (lcet10), 1.281
   (osdb), 1.135 (cubrim_src). Projected PPMd-class fix ≈ −20 % → rank ~7→2-3.
2. **Block-cap.** H-62 (`H-62-bwt-blocksize-lever.md`): the cubrim<bzip2 gap is **purely**
   the 64 KB BWT-block ceiling (u16 index) — cubrim@64 KB already *beats* bz2@100 KB on
   cubrim_src (103161<108910) and osdb (341396<393872); the rANS+geomix coder is
   *stronger* than bzip2 Huffman per-block, it just can't see enough context. The three
   **CHUNKED** text files (alice29, asyoulik, plrabn12) are the purest block-cap victims.

**Consilium question (B):** *Sequence the backend program — does H-62 (u16→u32 BWT index,
lift the 64 KB cap) ship BEFORE the multi-day H-61 PPMd build, and does H-62 alone move
the CHUNKED text files off rank 6?* **Predicted lever:** H-62 ≈ −12 % (proj: alice −13.1 %,
lcet −14.8 %, code −9.4 %, osdb −11.9 %) makes cubrim **beat bzip2 outright**, then H-61
stacks to PPMd-parity+. H-62 is flagged in-log as **highest ROI:effort of the backend
program**. Caveat (Gotcha #6): bigger block → O(n log n) SA cost compounds the >64 KB
perf flag; the build must address BWT/SA perf.

### Cluster C — Missing-transform-not-shipped (4 files, validated GO spikes)

**Files:** mr + x-ray (16-bit medical image), sao (fixed-width binary), ooffice (x86 exe).
Each has a **validated GO spike** whose only blocker is `codec.rs` integration + a
detector.

| file | spike | measured result | flips to |
|------|-------|-----------------|----------|
| **x-ray** | **H-60 MED16** (`H-60-med16-medical-image-grid.md`) | cub_MED16_LE 528903 vs cub_raw 586005 = **+9.74 %**, B/L 0.945 | **beats ppmd +5.5 %** (leader) |
| **mr** | **H-63 MED16** (`H-63-med16-mr-dicom-image-grid.md`) | cub_MED16_LE 202330 vs raw 236732 = **+14.53 %**, B/L 0.891 | **beats ppmd +10.9 %** (leader) |
| **ooffice** | **H-45 BCJ x86** (`H-45-BCJ-exe-grid.md`) | PE-dense .text B 288710 vs A 322674 = **+10.53 %**, B/L 0.988 | **beats leader (ppmd)** on .text |
| **sao** | **H-40-byteplane SoA W=28** (`H-40-binary-fieldsplit-grid.md`) | B 459034 vs A 484866 = **+5.33 %**, closes 56 % of gap, B/L 1.045 | closer, does **not** overtake xz → residual = backend |

**Signature.** The world-bench image gap (+38.4 % type-agg per H-60/H-63) is **fully a
missing-transform gap** for the two medical files — the shipped codec simply lacks MED.
mr and x-ray are the highest-confidence flips in the entire bench (both spikes beat the
*leader*, not just parity). ooffice similarly flips via BCJ. sao improves but its residual
is Cluster-B backend.

**Consilium question (C):** *Bundle the three leader-beating transforms (MED16 image,
BCJ exe, SoA byte-plane binary) into one "ship the validated grid" integration wave —
what is the minimal shared detector layer (image-geometry / e_machine-arch / fixed-width
stride) and the competitive-min wiring that guarantees byte-identical output on every
non-matching file?* **Predicted lever:** **4 files flip** (mr, x-ray, ooffice to
leader-beating; sao to gap-closed), zero regression by construction (all are competitive
`min(raw, transform)` + id byte, already proven byte-identical on tuned/holdout in each
spike). This is research-complete — pure integration.

### Cluster D — Binary / image edge cases at or near floor (2 files)

**Files:** kennedy.xls (binary·BIFF, gap 1.9 %, rank 2 — already ≈ xz), ptt5 (bilevel fax
image, gap 12.5 %).

**Signature.** kennedy.xls is **AT-FLOOR** — H-40-byteplane measured NO-GO on it (BIFF is
variable-record; de-interleave −96.55 %); cubrim already ≈ xz with no transform. Nothing
to do beyond generic backend micro-efficiency. ptt5 is **bilevel** — H-39 image grid
measured MED −2.21 % (NO-GO, subsumed: cubrim's BWT/LZ already captures the vertical fax
correlation). So ptt5's 12.5 % gap is *not* a missing 2D transform — it is the
Cluster-B backend gap wearing an image costume.

**Consilium question (D):** *Is there a bilevel/1-bit-raster transform beyond MED (e.g.
JBIG-style context template, arithmetic-coded G4) that is non-subsumed by cubrim's
existing vertical-correlation capture — or does ptt5 fold entirely into the H-61 backend
program?* **Predicted lever:** likely **fold into backend** (ptt5 ranks 4, already beats
zstd/ppmd — only xz/brotli lead by micro-efficiency); a JBIG context model is a
speculative new-class spike, low priority. kennedy.xls: accept floor.

---

## Prioritised consilium queue

Ranked by **(impact × files-fixed) / effort**. Impact = gap closed; files-fixed = count
moved off a losing rank; effort from the log's own GO-to-PLAN sizing.

| # | topic | cluster | files | effort | why this rank |
|---|-------|---------|-------|--------|---------------|
| **1** | **Ship the validated transform grid** (H-60/H-63 MED16 · H-45 BCJ · H-40 SoA) | C | **4** (mr, x-ray, ooffice, sao) | **Low** — research done, integration only | Only queue item that is *research-complete*; mr+x-ray+ooffice **flip to leader-beating**, guaranteed zero-regression via competitive min. Best ROI in the whole bench. |
| **2** | **H-62 larger BWT block** (u16→u32 index, lift 64 KB cap) | B | **11+** (all text/code/db; esp. 3 CHUNKED text) | **Medium** — arch change, must fix SA perf (Gotcha #6) | Log-flagged "highest ROI:effort of the backend program." Proj −12 %, makes cubrim beat bzip2 outright. Half the distance to ppmd for the *largest* cluster. Do before full PPMd. |
| **3** | **Tiny-file dispatcher fix** (route <64 KB off CUBE) | A | **5** (all rank-7 files) | **Low-Medium** — dispatch policy + small-block coder, no new transform | Fixes the ensemble's worst optics (5× dead-last). Target = brotli/gzip parity (H-39 says last 15 % is micro-ceiling), which still flips all 5 off rank 7. |
| **4** | **H-61 PPMd-class backend** (value-scheme `ppmd`, byte 13) | B (+ exe/binary residual) | **11+** deepened + sao/mozilla residual | **High** — multi-day genuine PPMd (order-4..6 + escape C/D + SEE); simple order-N is measured NO-GO (Gotcha #9) | Largest *ceiling* lift (text-agg 21.1 % is the biggest single number), takes rank 7→2-3 across text/code/db. Stacks on #2. Highest impact but gated by effort → after H-62 lands the cheap half. |
| **5** | **mozilla exe partial-BCJ + backend** | C/B | 1 | Medium | mozilla is code-*sparse* (H-45 measured mozilla-style slice −0.47 %, NO-GO) — BCJ helps only its dense .text spans; the rest is Cluster-B backend. Low marginal value; rides #1's detector + #4's backend. |
| **6** | **Bilevel-image / kennedy.xls edge** (Cluster D) | D | 2 | Low (mostly "accept floor") | ptt5 folds into #4 backend; kennedy.xls is at-floor. A JBIG bilevel spike is speculative — park until #1–#4 ship. |

**Net if queue #1–#4 execute:** the four MISSING-TRANSFORM files flip to leader-beating
(#1), the eleven text/code/db BACKEND files move from rank 5-6 toward rank 2-3 (#2+#4),
and the five TINY-FILE files leave rank 7 (#3) — i.e. **20 of 24 files** move off a losing
position, with kennedy.xls (at-floor) and mozilla/ptt5 (backend-residual) as the honest
long tail. That is the concrete path from "loses on all 24" toward the ensemble thesis:
**the right branch, detected per file, beats every rival.**

---

## Honesty notes (per project convention)

- Every number above is from `consilium/cubr-weakness-data.txt` (world-bench) or the cited
  H-NN spike report — **no estimated ratios**. Spike numbers are on the noted slices/regions
  (e.g. H-45 ooffice = dense .text slice, not the whole 6.15 MB file); direction transfers,
  absolute world-bench deltas require the shipped integration to re-measure.
- **Weak-baseline caveat (CUBR-REEVAL):** several GO spikes were first stated vs zstd-19;
  the ones cited here (H-60/H-63/H-45/H-40 byte-plane) are measured vs the **strong**
  universals (xz-9e / PPMd / brotli-q11), which is the correct bar for this bench. H-60/H-63
  beat *ppmd* (the actual world-bench leader on image), so those flips are honest.
- The BACKEND-CEILING axis is a **shared** lever: one PPMd-class backend (H-61) + one
  block-cap lift (H-62) lift text, code, database, *and* the sao/mozilla transform-residuals
  simultaneously — which is why they dominate the queue despite having no per-file transform.
- No code, no spikes were run for this artefact — it is a planning map over existing
  measurements.
