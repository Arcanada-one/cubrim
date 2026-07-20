# CUBR-0001 QUEUE#1 — ship the validated transform grid into codec.rs

**First real codec change.** Bundled the three leader-beating validated type-gated transforms into `code/cubrim-rs/src/codec.rs` behind the competitive-min rail, each as a new self-describing container mode with an auto-detector:

| mode | id | transform | detector | validated in |
|---|---|---|---|---|
| `MODE_MED16` | 7 | 16-bit grayscale MED predictor (2-byte-LE residual) | row-width by min vertical-abs-diff + sharp-dip confidence gate | H-60 (x-ray), H-63 (MR/DICOM) |
| `MODE_BCJ` | 8 | x86 E8/E9 + ARM64 BL branch-conversion | ELF `e_machine` / PE machine field | H-45 (x86), H-57 (ARM64) |
| `MODE_SOA` | 9 | byte-plane Structure-of-Arrays de-interleave | fixed record width by min lag-W abs-diff + sharp-dip gate | H-40 (sao) |

**Zero-regression by construction.** Each mode is emitted only via `if x.len() < best.len()` inside `encode_with_config_inner` (competitive min), gated `>cube_size_limit` (64 KB), and requires its detector to fire — so every non-matching input is **byte-identical** to the prior codec. Each new mode has a wire id + fail-closed bounds-checked decoder branch. Round-trip is byte-exact (property tests added).

## Wire formats (header.rs)
- MODE_MED16: `[MAGIC][VER][7][orig_len 4B][width_px 2B BE][tail_byte 1B]` + nested residual sub-blob.
- MODE_BCJ: `[MAGIC][VER][8][orig_len 4B][arch 1B]` + nested filtered sub-blob.
- MODE_SOA: `[MAGIC][VER][9][orig_len 4B][width 2B BE]` + nested transposed sub-blob.

---

# Throughput hardening — make the big-file bwt-rans path finish in time

The transform grid above made the 4 target big files compress *well*, but the champion
rail (`--value-scheme bwt-rans`) was **too slow to run the corpus**: the full 8.47 MB x-ray
did not finish in 6 minutes on the handoff (serial-block) codec. This pass profiled and
sped up the `bwt-rans` encode path. Every change below is either **byte-identical** or a
measured **≤0.04 %** ratio delta, and every one keeps round-trip byte-exact.

## Root causes (profiled, not guessed)

Profiling one 64 KB x-ray block and the whole-file candidate breakdown found four
multiplicative costs, none of them the cube geometry:

1. **Double encode per block.** `estimate_cube_size` runs the *entire* 8-coder rANS-family
   competition (via the `*_size` helpers, each of which fully encodes) just to make the
   raw-vs-cube decision — then Step 7 runs all 8 coders **again** to emit. Every block
   encoded twice.
2. **Serial block loop.** `encode_chunked` looped its independent ≤64 KB blocks one at a
   time on a single core; the machine's other 11 cores sat idle.
3. **Geomix parameter sweep.** `BwtGeoMix` (the winner on ~100 % of x-ray/mr/sao blocks)
   swept `GM_INCS × GM_LRS` = 4 full context-mixing passes per block; ~74 % of a block's
   coder time. The chosen `(inc, lr)` is serialized in the block header, so the sweep is a
   pure encoder-side knob — decode never depends on it.
4. **Serial LZ pre-pass.** The whole-file `encode_lz_prepass` runs a largely
   single-threaded optimal-DP parse and two container builds; it loses on medical/scientific
   data (Gotcha #8) yet ran sequentially after the block encodes.

## Fixes (all round-trip byte-exact; ratio-neutral or ≤0.04 %)

- **Eliminate the double encode.** The rANS-family value stream is now built **once**
  (`encode_rans_family_value_stream`) and reused for both the raw-vs-cube size decision and
  the emitted bytes. **Byte-identical output**, ~2× less work per block.
- **Parallelise the block loop.** `encode_blocks_parallel` fans the independent chunk
  blocks across all cores with scoped threads + an atomic work-stealing cursor, reassembling
  in strict block order. **Byte-identical wire format.** (std-only; compiles on the pinned
  rustc.)
- **Trim the geomix sweep on the big-file path only.** Block-encode worker threads set a
  thread-local that narrows the sweep to the single dominant combo `(inc=32, lr_idx=0)`.
  Measured vs the full 4-combo sweep: **x-ray 0.000 %, mr +0.017 %, sao +0.036 %.** Standalone
  ≤64 KB single-block inputs (the frozen leaderboard) keep the exhaustive sweep and stay
  **byte-identical** (the thread-local is never set off the chunked path).
- **Overlap the serial LZ pre-pass.** LZ + columnar run on one background thread so their
  single-threaded parse overlaps the block-parallel transform encodes. **Byte-identical
  output** (still the exact competitive `min()`), only the scheduling changes.

A tried-and-**reverted** aggressive gate (skip LZ/columnar/SoA when a 16-bit/float domain
transform matched) is documented here as a dead end: the `med16`/`binfloat` detectors
false-match CSV and repetitive data, and skipping the generic pre-passes there **regresses**
ratio (7 unit tests caught it — `columnar`/`chunked` families). There is no *cheap* proof
that LZ loses on a given input, so LZ is kept and merely overlapped.

## Result — total CPU work and wall time

Machine-independent metric (CPU-seconds = user+sys), full 8.47 MB x-ray, `--value-scheme bwt-rans`:

| stage | CPU-seconds | note |
|---|---|---|
| handoff (serial blocks) | ~1750 | did **not** finish in 6 min |
| + all fixes above | **484** | **3.6× less work** |

Wall time is core-bound: **484 core-seconds ⇒ ~40 s at full 12-core parallelism (< 60 s target).**
Measurements below were taken on a **shared, heavily loaded host** (a concurrent `paxbt`
workload held ~4–8 cores throughout), so the observed walls reflect ~4 effective cores, not
the code's ceiling:

| file | wall (loaded host) | CPU-s | CPU% | RT |
|---|---|---|---|---|
| x-ray | 2:09 | 484 | 375 % | OK |
| mr | 2:12 | 489 | 370 % | OK |
| ooffice | 1:08 | 341 | 500 % | OK |
| sao | 1:34 | 442 | 472 % | OK |

`cargo test` = **249 passed** (7 suites); round-trip byte-exact on all four files.

## Before/after world-bench (the 4 target files)

Ratios are `compressed/original` on the champion rail (`--value-scheme bwt-rans`). The "old"
column is the committed leaderboard (`code_sha 6f76826`, pre-MED16); "new" is the integrated
codebase measured this pass (MED16 lands the x-ray/sao gains; the throughput fixes preserve
them within ≤0.04 %).

| file | orig | out (new) | old ratio | **new ratio** | rank | beats ppmd | best archiver |
|---|---|---|---|---|---|---|---|
| **x-ray** | 8 474 240 | 3 771 607 | 0.509444 | **0.445067** | 3 → **1** | **yes** (ppmd 0.454471) | **cubrim** |
| **sao** | 7 251 944 | 4 528 374 | 0.684659 | **0.624436** | 5 → **2** | **yes** (ppmd 0.656107) | xz 0.610272 |
| mr | 9 970 564 | 2 532 936 | 0.254021 | 0.254041 | 3 → 3 | no (ppmd 0.230793) | ppmd |
| ooffice | 6 152 192 | 2 680 603 | 0.435461 | 0.435715 | 5 → 5 | no (xz 0.394529) | xz |

- **x-ray**: cubrim is now the **outright best** archiver (beats gzip/bzip2/xz/zstd/brotli/ppmd) — the MED16 flip confirmed at full 8 MB scale.
- **sao**: cubrim jumps to **rank 2** and beats ppmd (xz still leads).
- **mr / ooffice**: unchanged; mr remains a ppmd-favourable file (cube+MED does not beat PPMd's order-N model) and ooffice stays an xz/LZ file. Both are honest non-wins — reported as-is.

## Code SHA

_stamped at commit — see `git log` for this report's commit._
