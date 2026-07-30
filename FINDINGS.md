# CUBR-0087 — speed and memory: measured findings

Running record. Every number here was produced on this host by the command shown
and can be re-run. Numbers that are *derived from source reading* rather than
measured are labelled as such, and never enter the DB as measurements.

Base: `origin/release/cubrim-1-0.3.x` @ `09ef2bb` (= tag `v0.3.2`, the shipped
binary and the engine behind DB `meta_id=35`). **Not** `main` — see CUBR-0089.

---

## F0 — the baseline was reproduced, and the gaps are larger than the brief stated

`meta_id=35`, `is_current=t`, scope `overall`, 314,749,364 bytes:

| archiver | ratio | compress MiB/s | decompress MiB/s | peak RSS MiB |
|---|---|---|---|---|
| **cubrim** | **0.1890** | **0.0226** | **0.093** | **18,439** |
| ppmd | 0.2286 | 9.2698 | 8.452 | 263 |
| xz | 0.2344 | 1.5996 | 71.832 | 673 |
| 7z | 0.2355 | 2.8640 | 83.375 | 682 |
| brotli | 0.2408 | 0.4479 | 294.057 | 238 |
| zstd | 0.2490 | 1.5060 | 478.733 | 771 |

Three competitor figures in the operator's brief do not match the DB: ppmd
compress (briefed 5.555, DB 9.2698), ppmd ratio (briefed 0.2275, DB 0.2286) and
zstd decompress (briefed 335.79, DB 478.733). The DB is authoritative. The
correction makes the gaps **worse**, not better:

- encode **410×** slower than ppmd (not 240×), **877×** slower than rar;
- decode **5,148×** slower than zstd (not 3,600×), **7,980×** slower than lz4;
- memory **70×** ppmd.

The ratio lead being protected is real: 0.1890 vs 0.2286 is a **17.3% relative**
advantage, and Cubrim is the only entrant below 0.2.

---

## F1 — 75% of the 18.4 GB peak is one allocation decision, and it is derived, not measured

*Source reading, `src/cm2.rs`.* CM2 sizes every model table from the input
length: `tbits_for(len) = clamp(ceil_log2(len) + 3, 18, 27)`. Any input ≥ 16 MB
therefore gets the maximum, `tbits = 27`.

Each `Ctr` holds `t: Vec<u16>` + `c: Vec<u8>` + `st: Vec<u8>` = **4 bytes × 2^tbits**.
`CmModel` allocates 24 of them (12 orders + 6 sparse + indirect + 4 word tables
+ optional column) plus three `Match` tables at `Vec<u32>` = 4 bytes × 2^tbits:

| tbits | per-Ctr | ×24 | 3×Match | model total |
|---|---|---|---|---|
| **27 (shipped cap)** | 512 MiB | 12.0 GiB | 1.50 GiB | **13.50 GiB** |
| 26 | 256 MiB | 6.0 GiB | 0.75 GiB | 6.75 GiB |
| 25 | 128 MiB | 3.0 GiB | 0.38 GiB | 3.38 GiB |
| 24 | 64 MiB | 1.5 GiB | 0.19 GiB | 1.69 GiB |
| 23 | 32 MiB | 0.75 GiB | 0.09 GiB | 0.85 GiB |
| 20 | 4 MiB | 96 MiB | 12 MiB | 0.11 GiB |

13.50 GiB against a measured peak of 18,439 MiB (18.01 GiB) = **75% of the entire
peak RSS is the CM2 model tables**. The source-derived figure was then checked
against a live run: `dickens.2m` (2 MB ⇒ `tbits = 24` ⇒ predicted 1.69 GiB)
measured **1,661,044 KiB = 1.58 GiB** encode peak and 1,543,040 KiB decode peak.
Prediction and measurement agree, so the table above is trustworthy as the
explanation of the 18 GB.

The comment at the allocation site already says "~12 GB/model at the max" — the
cost was known, chosen deliberately for "the collision-free ratio win", and never
priced against the ratio it buys. **That price is what the sweep now measures.**

> Note for any future memory knob: the decoder derives `tbits` from `orig_len`
> using the *same* function, so the table size is **not in the wire format**. A
> shipping memory option must record the exponent in the header or bind it to a
> preset byte. The sweep override is therefore sweep-only and is documented as
> such at the call site.

---

## F2 — the encode/decode asymmetry is inside CM2, not in the outer competitive rail

The consilium flagged "encode is 4.11× slower than decode in a symmetric
context-model codec" as the largest unexplained number on the board, and the
leading hypothesis (mine included, from reading `encode_with_config_inner`) was
the outer competitive-min rail: the encoder builds ~13 candidate encodings and
the decoder replays one.

**Measured, and the hypothesis is wrong for text.** Candidate attribution on
`dickens.2m` (`CUBRIM_PROFILE=1`, encode wall 140.0 s):

| candidate | calls | seconds | share | wins | out bytes |
|---|---|---|---|---|---|
| `cm2` | 1 | 138.384 | **98.81%** | 1 | 461,437 |
| `lz_prepass` | 1 | 38.658 | 27.60% | 0 | 649,256 |
| `geocm` | 1 | 1.395 | 1.00% | 0 | — |
| `base` | 1 | 0.218 | 0.16% | 0 | 1,756,742 |
| `columnar`, `med16`, `soa`, `record_cm`, `binfloat`, `bcj`, `cm`, `vcf`, `bcj_cm2` | 1 each | ≤0.018 | ≤0.01% | 0 | — |

The outer rail is **not** the encode-side waste. Every detector-gated candidate
declines in microseconds, and the one expensive loser — the LZ pre-pass at
38.7 s — runs on a background thread and is entirely hidden behind `cm2`'s
138.4 s, so its wall-clock cost is zero. `cm2` is simultaneously 98.8% of the
cost **and** the winner.

The asymmetry is one level down. `cm2_encode` (`src/cm2.rs`) runs the full CM2
encode **once for the base model plus once per candidate column delimiter**
(`detect_col_delims`, `MAX = 2`), keeping the smallest — while `cm2_decode`
replays exactly the one variant recorded in the blob header. Up to **3 full
passes at encode against 1 at decode** explains the measured 140.0 s / 51.4 s
= 2.7× on this file, and the corpus-level 4.11×.

This relocates the lever and kills a plausible-but-wrong plan:

- Gating or parallelising the outer candidate list buys **~0%** on text. Anyone
  reading the code would have expected several hundred percent.
- The FH4-03 column-variant sweep is the encode-side lever, and it is
  **wire-compatible to disable** (the column model and its delimiter live in the
  blob's length header), so unlike the table-size cap it is a legitimate preset
  candidate rather than a sweep-only override.
- Whether it should be disabled depends entirely on how much ratio those extra
  passes buy. That is now instrumented per variant (`cm2_variant_base` /
  `cm2_variant_col` with per-variant time, size and win count) and priced by the
  sweep's `nocol` row.

---

## F2b — on non-text data the outer rail *is* the waste, and it is far larger than F2

F2's conclusion ("the outer rail costs ~0%") is **true only for text**. The same
instrument on `ooffice.2m` (a 2 MB slice of the Silesia executable) inverts it.
Encode wall 207.1 s; candidate CPU time far exceeds that because blocks encode in
parallel, so read the seconds column as CPU attribution:

| candidate | calls | CPU seconds | wins | note |
|---|---|---|---|---|
| `vs_ctxmix` | 384 | 461.06 | 384 | inner value-stream competition |
| `vs_geomix` | 384 | 406.28 | 384 | inner value-stream competition |
| `vs_order2_rans` | 384 | 253.41 | 384 | inner value-stream competition |
| `base` | 14 | 90.00 | **0** | the cube/BWT path — **never wins** |
| `med16` | 1 | 89.72 | 1 | superseded downstream |
| `cm2` | 1 | 62.68 | 1 | superseded downstream |
| `bcj_cm2` | 1 | 50.52 | 1 | **final winner, 677,605 bytes** |
| `vs_bwt_huff` | 384 | 41.38 | 384 | inner |
| `vs_bwt_rans` | 384 | 30.16 | 0 | inner |
| `lz_prepass` | 1 | 29.69 | 0 | hidden on background thread |
| `vs_adaptive` | 384 | 29.16 | 0 | inner |
| `vs_t4_huff` | 384 | 22.24 | 373 | inner |
| `vs_lz_rans` | 384 | 15.32 | 0 | inner |
| `geocm`, `bcj`, `soa`, `columnar`, `record_cm`, `binfloat`, `vcf`, `cm` | — | ≤3.58 | 0 | detectors decline cheaply |

The eight-way value-stream competition inside `base` costs **~1,258 CPU-seconds**
on a 2 MB file. `base` is called 14 times — once at top level and once more each
time a nested transform re-enters the encoder — and each call re-runs the full
per-block competition over ~32 blocks, hence 384 inner calls.

**All of it loses.** The emitted blob is `bcj_cm2`'s 677,605 bytes. `base`'s own
output across its calls totals 29,226,029 bytes — worse by a factor of ~43. The
inner competition faithfully picks the best of eight schemes for a container that
is then discarded whole.

So the two data classes have **different bottlenecks, and neither is the entropy
coder**:

- text (`dickens`): one backend (CM2) is 98.8% of encode, and the encoder-side
  redundancy is CM2's own 1+2 variant sweep (F2);
- executable (`ooffice`): the winner costs 50.5 s of a 207.1 s wall, and the
  dominant cost is a candidate path that cannot win.

This also revises the brief's central diagnostic. "The profile is nearly flat
across data types, therefore the cost is in the shared per-symbol path" does not
survive attribution: the per-type speeds are similar for *different reasons*, and
the per-symbol coder is a small part of both. A lever aimed at the coder would
have moved neither file.

### The lever this opens, and why it can be byte-exact

Competitive-min is the project's regression-proofing and must not be weakened.
But a candidate only matters if it *wins*, and a candidate that has already
emitted more bytes than the incumbent cannot win. That admits **branch-and-bound
with provably identical output**: run the cheap strong candidates first, pass the
incumbent size down as a bound, and abandon a candidate the moment its partial
output reaches that bound.

Two subtleties that make the difference between correct and almost-correct:

1. **Ties.** The existing rail keeps the *strictly smaller* candidate, so ties
   resolve to the earlier-listed one. Aborting on `partial >= bound` is only safe
   for candidates that sit *later* in the documented priority order than the
   current incumbent; for an earlier-listed candidate the abort must use
   `partial > bound`. Get this wrong and output changes on ties — silently, and
   only on some files.
2. **The fallback guarantee.** `base` is also the R7 raw-store safety net that
   bounds expansion. Abandoning the *expensive value-stream competition* does not
   abandon raw-store, which is what actually provides the guarantee.

## F2c — the CM2 variant sweep, priced

`osdb.2m` (Silesia database slice, 2 MB), encode wall 228.9 s, with the
per-variant instrument in place:

| candidate | calls | CPU seconds | wins | out bytes |
|---|---|---|---|---|
| `cm2` (total) | 1 | 188.70 | 1 | 472,809 |
| ├ `cm2_variant_base` | 1 | 57.24 | 1 | 496,824 |
| └ `cm2_variant_col` | 2 | 131.35 | 1 | 962,199 (two variants) |
| `record_cm` | 1 | 35.31 | 1 | 563,034 |
| `lz_prepass` | 1 | 23.11 | 0 | 683,236 |
| `base` | 2 | 0.73 | 0 | 4,195,412 |
| everything else | — | ≤4.16 | 0 | — |

The trade is now a number instead of an assumption:

- base variant alone: **496,824 bytes in 57.24 s**
- plus the two column variants: **472,809 bytes in 188.70 s**

**The FH4-03 column sweep buys −4.83% on the CM2 stream for 3.30× the CM2
encode time.** Nobody had priced it; it was added as a competitive-min candidate,
which guarantees it cannot *hurt ratio* and says nothing about what it costs.

That is a defensible thing to pay for a `--max` preset and an indefensible
default for anyone compressing a working set. It is also the cleanest possible
input to Phase C: `--balanced` skips the column variants (wire-compatible, so
archives stay mutually decodable) and buys back most of a factor of three on
database- and text-class data at a stated ~5% ratio cost.

Note also that `base` costs 0.73 s here against 90 s on `ooffice`. The outer-rail
waste is **specific to executable-class data**, where a nested transform wins and
the cube path is re-run inside every candidate. Three files, three different cost
centres, and the entropy coder is not among them.

## F3 — the falsifiable prediction the brief asked for, and what it now implies

The task description records a prediction to test each lever against: *work
removed from the shared per-symbol path should move all scopes together; a lever
that speeds up one scope only did not touch the shared path.*

F2 sharpens this. The "shared per-symbol path" is not shared across scopes the
way the flat profile suggested — it is CM2's per-bit mixer **on the files CM2
wins**, and a different backend elsewhere. `dickens` (text) spends 98.8% in CM2.
The per-scope profile must therefore be read as "which backend won", not "one
path costs the same everywhere", and the `code` scope outlier at 0.0850 MiB/s
(M4) is most likely a scope where CM2 does not win or is not gated on. That is
now a cheap check rather than a mystery: run the attribution per scope and read
which candidate took the time.

---

## F4 — the `code` 0.0850 outlier is one file, and the likely cause unifies it with F2c

M4 asked why the `code` scope runs at 0.0850 MiB/s against a 0.0119–0.0250 band.
The DB answers the first half immediately — the scope is three files and one of
them is 99.9% of the bytes:

| file | bytes | encode s | MiB/s | peak RSS MiB |
|---|---|---|---|---|
| silesia/samba | 21,606,400 | 242.1 | **0.0851** | 13,902 |
| canterbury/grammar.lsp | 3,721 | 0.0 | 0.0776 | 30 |
| canterbury/fields.c | 11,150 | 0.4 | 0.0294 | 35 |

So "the `code` type is fast" is really "`samba` is fast". Its 13,902 MiB peak
proves CM2 *did* run with full-size tables (`tbits = 27`), so the speed is not
explained by skipping the strong backend.

**CONFIRMED DIRECTLY — see the measurement at the end of this section.**

**Prediction (falsifiable, and the sweep tests it without new work):** the
difference is F2c's column-variant sweep failing to trigger. `detect_col_delims`
accepts a byte only if its inter-occurrence gaps have coefficient of variation
≤ 1.2 over a 256 KiB sample — a genuinely periodic delimiter. A tar of C sources
has no such byte; a database dump, XML and even prose do. On `osdb` that sweep
costs 3.30× the CM2 encode time. If it simply does not fire on `samba`, `samba`
should be ~3× faster than its peers *for that reason alone* and for no reason
that generalises.

### The direct measurement, and it lands on the prediction

Attribution on a 2 MB `samba` slice, dev-ai, same binary as every other row:

| candidate | calls | seconds | share | wins | out bytes |
|---|---|---|---|---|---|
| `cm2` | 1 | 23.434 | 97.44% | 1 | 377,987 |
| `cm2_variant_base` | 1 | 23.419 | 97.37% | 1 | 377,981 |
| `lz_prepass` | 1 | 7.128 | 29.64% | 0 | 509,645 |
| `geocm` | 1 | 0.507 | 2.11% | 0 | — |
| `base` | 1 | 0.069 | 0.29% | 0 | — |

**There is no `cm2_variant_col` row.** Not a small one — absent. The instrument
emits a row for every candidate that runs, so its absence is the measurement:
`detect_col_delims` proposes nothing on a tar of C sources, and the sweep never
fires. `cm2` total (23.434 s) and `cm2_variant_base` (23.419 s) agree to 15 ms,
which is the same statement from the other side: the base pass *is* the whole of
CM2 here.

The arithmetic closes it:

| file | sweep fires? | encode wall, 2 MB | MiB/s |
|---|---|---|---|
| dickens (text) | yes, 2 extra passes | 80.8 s | 0.0248 |
| dickens, `--preset balanced` | suppressed | 26.9 s | 0.0744 |
| **samba (code)** | **never proposed** | **24.1 s** | **0.0832** |

`samba` at 24.1 s sits alongside `dickens` with the sweep suppressed at 26.9 s,
and the measured 0.0832 MiB/s reproduces the DB's `code`-scope 0.0851 MiB/s. So
the outlier was never a property of source code as data — **`samba` was simply
not paying for a sweep everything else was paying for**, and `--preset balanced`
is exactly the knob that brings the other classes to it.

M4 is closed by measurement rather than by inference, and it turned out to be the
same finding as F2c seen from the other end.

## F5 — all five classes attributed: two cost centres, and the entropy coder is neither

2 MB slices, `CUBRIM_PROFILE=1`, every row round-tripped byte-exact:

| file | class | ratio | enc wall s | dec wall s | winner | dominant cost | outer-rail waste |
|---|---|---|---|---|---|---|---|
| dickens | text | 0.2200 | 140.0 | 51.4 | `cm2` | `cm2` 98.8% | negligible (`base` 0.16%) |
| xml | xml | 0.0760 | 176.1 | 69.2 | `cm2` | `cm2` 98.8%, col sweep 68.5% | negligible (`base` 0.12%) |
| osdb | database | 0.2255 | 228.9 | 46.8 | `cm2` (col variant) | `cm2` 82.4%, col sweep 57.4% | negligible (`base` 0.32%) |
| ooffice | exe | 0.3231 | 207.1 | 55.8 | `bcj_cm2` | `base` 43.5% + winner 24.4% | **large** |
| x-ray | image | 0.4188 | 111.1 | **2.6** | `med16` | `base` 73.5% + `med16` 73.5% | **large** |

Two cost centres, cleanly split by which backend wins:

1. **CM2-won files (text / xml / database) — the column-variant sweep.**
   Priced per file: `xml` 160,517 → 159,384 bytes (**−0.71%**) for **2.27×** the
   CM2 encode time; `osdb` 496,824 → 472,809 (**−4.83%**) for **3.30×**.
2. **Transform-won files (exe / image) — the cube/BWT `base` path.** 43.5% and
   73.5% of encode wall on a candidate that loses the top-level competition by
   43× and 14× respectively. Its per-block eight-way value-stream competition
   burns ~1,100–1,260 CPU-seconds per 2 MB file doing correct work on a container
   that is discarded whole.

**The entropy coder is not a cost centre in any of the five.** `cm2`, `base` and
`med16` account for 98%+ of every profile, and within `cm2` the cost is the
per-bit mixer over 24 model tables, not the range coder that consumes its output.

This is the answer to Phase A's question, and it is a **refutation of the headline
lever**. NEW-22 proposed interleaved N-way SIMD rANS with a target of ≥500 MB/s
decode on the entropy stage. Measured, there is no class in which the entropy
stage is the constraint, so an infinitely fast rANS moves nothing. The consilium
pre-registered the kill rule — *coder share < 25% ⇒ NEW-22 is cancelled on the CM
path, not descoped* — and the measurement fires it. rANS interleaving survives
only as a possible non-CM fast tier, which is a different product.

The honest cost of learning this: one instrumented encoder (~130 lines, byte-
neutral — verified by sha256 identity on `xml`) and five 2 MB encodes, about 15
minutes of machine time. It replaced a plan that would have spent weeks on SIMD.

## F6 — the encoder oversubscribes the machine, and it showed up as collateral damage

Observed while sequencing this work: **two** concurrent `cubrim compress`
processes on a 16-core host drove the load average to **82**.

The mechanism is in `encode_blocks_parallel`: it spawns
`available_parallelism()` threads (16 here), and every nested candidate encode —
`encode_bcj`, `encode_med16`, `encode_soa`, the LZ pre-pass on its own background
thread — re-enters the encoder and spawns its own full-width pool. Nesting depth
multiplies rather than shares, so a single file encode can put well over a
hundred runnable threads on 16 cores.

The code already anticipates part of this. `encode_with_config_inner` explains
that the LZ/columnar pre-passes get *one* background thread rather than one per
candidate because "fanning every candidate out separately measurably hurts under
load" — the right instinct, applied to one call site while the general case stays
unbounded.

Two consequences, and the second is the one that matters for the product:

1. **It corrupted my own measurement plan.** The first sweep attempt had to be
   abandoned and re-armed behind a load gate, because under load 82 the rows
   would have differed by scheduling noise rather than by the variable under
   test. Recorded because it is the honest cost of the mistake, not hidden.
2. **Cubrim is a bad neighbour.** An archiver that saturates a shared machine
   several times over is not "industrially usable" regardless of its throughput
   number, and on a contended host the oversubscription costs throughput too
   (context switching and cache thrash against 24 hash tables that are already
   memory-latency-sensitive).

There is already a `CUBR_THREADS` override, so the knob exists; what is missing is
a **global** budget shared across nesting levels instead of a per-level
`available_parallelism()`. Logged as lever **L3** and unmeasured so far — it is
listed below as a candidate, not as a result.

### The two levers, and what each is allowed to cost

| lever | targets | ratio cost | wire compatible | status |
|---|---|---|---|---|
| **L1** branch-and-bound: defer `base`, bound it by the incumbent, abandon when partial > bound | exe, image | **none — byte-identical by construction** | yes (output unchanged) | implemented; identity gate **3/3 PASS** (below) |
| **L2** skip the FH4-03 column variants | text, xml, database | −0.7% to −4.8% output size | yes (column flag lives in the blob header) | knob implemented; sweep pending |

| **L3** global thread budget shared across nesting levels instead of per-level `available_parallelism()` | all classes, and shared-host behaviour | expected none | yes | **UNMEASURED — attempted and abandoned, see below** |
| **L4** CM2 table-size budget (`tbits`) as a preset-bound memory knob | memory on every CM2-won file | unknown until swept | **no** — the exponent is not in the wire format; needs a header field or preset byte first | knob implemented for sweeping only |

L1 is unconditional: it costs nothing and can ship as the default. L2 costs ratio
and therefore belongs to a preset, never to `--max`. L3 is expected to be free but
is **not yet measured**, and is listed as a candidate so it is not mistaken for a
result. L4 cannot ship in its current form at all: the sweep override changes a
value the decoder re-derives from `orig_len`, so an archive written under one cap
is only readable under the same cap. That is a wire-format change, and it is
called out here rather than discovered later by someone whose archive stops
opening.

## F7 — L1's byte-identity gate: 3/3 identical, including the case where the bound fires

The claim "branch-and-bound changes no emitted byte" is an argument, and an
argument about ties and abandonment order is exactly the kind that is convincing
and wrong. So it is gated on sha256, against blobs produced by the pre-change
build, with a round-trip on each:

| file | reference bytes | new bytes | sha256 | round-trip |
|---|---|---|---|---|
| dickens.2m | 461,437 | 461,437 | `c8aed8ae4c39d8a463e3…` identical | PASS |
| ooffice.2m | 677,605 | 677,605 | `4d563b48ae509f11b65b0c71…` identical | PASS |
| osdb.2m | 472,809 | 472,809 | identical | PASS |

`ooffice` is the load-bearing row: it is the file where `base` loses by 43× and
therefore the one where the bound actually fires and blocks are abandoned
mid-flight. Its blob is byte-for-byte what the unbounded encoder produced.

`dickens` and `osdb` matter for the opposite reason — on those, `base` is 0.16%
and 0.32% of encode, so nothing should be abandoned, and the gate confirms the
change is inert where it should be inert.

### Re-run at full corpus scale after the F8 fix

The slice gate above was run against the *broken* implementation, so it was
re-run from scratch on whole Silesia files with the corrected build:

| file | bytes in | reference | new | identity | round-trip |
|---|---|---|---|---|---|
| ooffice (exe) | 6,152,192 | 1,763,460 | 1,763,460 | **IDENTICAL** ×2 hosts | PASS |
| x-ray (image) | 8,474,240 | 3,637,036 | 3,637,036 | **IDENTICAL** ×2 hosts | PASS |
| samba (code) | 21,606,400 | 3,138,929 | 3,138,929 | **IDENTICAL** ×2 hosts | PASS |

**All three files were run to completion independently on `arcana-devs` (16
cores) and on `dev-ai` (64 cores)**, and both hosts produced the same byte counts
and the same identity verdict on every one. That is worth more than a repeat
on one machine: it rules out a host-specific accident, and it matters here
because the encoder's abandonment path is racy by design — a different core count
schedules the worker threads differently, so the two runs did not abandon the same
blocks at the same moments and still emitted identical bytes.

Both **load-bearing** cases now pass at real scale: `ooffice` and `x-ray` are the
two classes where a type transform wins and `base` therefore loses the top-level
competition, so they are the only files where the bound actually fires and blocks
are abandoned mid-flight. At 6 MB and 8 MB these are ~94 and ~130 blocks against
the slices' ~32, which is where the abandonment race between worker threads has
room to misbehave.

**Gate complete: 3/3 IDENTICAL with round-trip PASS at full corpus scale**, across
all three classes that matter — the two where the bound fires (`ooffice`, `x-ray`)
and one 21.6 MB / ~330-block file to exercise the abandonment race at depth.

**Still not proven, and it should be before this is treated as settled:**

- Nothing has been run at `enwik8` scale (100 MB, ~1,500 blocks), where the model
  is also 8× larger than anything tested here.
- The gate compares against a reference binary built from the same tree with the
  knobs unset. It proves the *change* is inert; it says nothing about whether the
  codec was correct to begin with.
- The suite's six pre-existing failures mean a fresh clone still cannot go green,
  so "tests pass" is not yet a statement anyone else can reproduce.

Until those three close, L1 is *measured correct on three files*, which is not the
same as correct.

## F8 — L1's first implementation was wrong, the identity gate could not see it, and the test suite could

`cargo test --release` on the L1 tree: **285 passed, 26 failed**. Every failure was
on a chunked or large-file path — `test_chunked_round_trip_various_sizes`,
`test_bwt_*_corpus_round_trip_all_files`, `test_mode_lz_*`, `test_columnar_*`,
`test_binfloat_*`, `geocm_roundtrips_and_fails_closed`, and the rest.

**Root cause.** The bound was held in a process-global `AtomicUsize`. The
justification was that a bound which only ever decreases can never cause a
regrettable abandonment — which is true for *one* encode and false for a library.
`encode` is a public entry point, callers run it concurrently, and the crate's own
test suite does exactly that. A small bound set by one test's encode abandoned
another thread's `base`; that encode had no incumbent of its own, so `best` was
still the empty "not computed yet" marker, and **`encode` returned an empty blob**.

Two things worth keeping from this:

1. **The byte-identity gate passed at the same time.** All three files were
   byte-identical with round-trip PASS, including `ooffice` where the bound fires.
   It could not fail: the CLI runs one encode per process, so the gate never
   exercised the failure mode. A gate that exercises one concurrency level cannot
   clear a change whose failure mode is concurrency — the gate was necessary and
   not sufficient, and I would have shipped on it.
2. **The "no incumbent" case was unguarded.** Even single-threaded, if `base` is
   the only candidate and is abandoned, there is nothing to fall back on. The
   global version had no way to express "there is no bound here".

**Fix.** The global is gone. The bound is an explicit `EncBound` parameter through
`encode_base_bounded` → `encode_chunked_bounded` → `encode_blocks_parallel`, so
there is no shared mutable state, no cross-encode leakage, and the bound a
candidate is measured against is the one its own caller set. `usize::MAX` means
unbounded, which is what the no-incumbent case now passes, and a `debug_assert`
states the invariant that the large-file path always produces a candidate.

Both gates must now be re-run from scratch — identity **and** tests. Nothing about
L1 is proven until they are both green together.

## F9 — the model footprint is a **decoder** requirement, and it blocks the web-codec epic

F1 treated 13.50 GiB as an encoder memory problem. It is not only that. The
decoder rebuilds the same tables, because `cm2_decode` derives `tbits` from
`orig_len` with the same `tbits_for`. From the DB (`meta_id=35`, cubrim):

| scope | decode peak RSS MiB | encode peak RSS MiB |
|---|---|---|
| type:database | **12,561** | 12,798 |
| corpus:silesia | **12,561** | 13,902 |
| overall | **12,561** | 18,439 |
| type:exe | 12,368 | 12,619 |
| type:code | 12,315 | 13,902 |
| type:text | 11,608 | 18,439 |
| corpus:enwik8 | 11,608 | 18,439 |
| type:image | 88 | 10,770 |

**Decoding a Cubrim archive of a ≥16 MB file needs ~12.3 GiB of RAM.** That is not
a preference, it is a hard requirement of the format as shipped, because the table
exponent is not in the wire format — the decoder has no way to be told to use less.

The consequence lands outside this task:

- **`CUBR-0077` (WASM decoder proof of concept) cannot succeed as specified.**
  `wasm32` has a **4 GiB** address-space ceiling; the decoder needs three times
  that for a file of ordinary size. No amount of decoder optimisation reaches it —
  the tables are allocated before any decoding happens.
- `CUBR-0075`'s acceptance criteria include **bounded decoder memory**, which the
  current format cannot provide at any setting.
- `CUBR-0078`/`CUBR-0079` (reverse proxy, browser technology preview) inherit the
  same ceiling.

So the wire-format change that lets a blob declare its table exponent is not a
nice-to-have for a memory preset — it is a **prerequisite for the entire web-codec
epic**, and it is cheap relative to what depends on it. This reframes L4 from
"optional preset" to "blocking dependency", and it is the strongest argument in
this document for doing it.

What is *not* yet known, and what the running sweep answers: **how much ratio the
smaller tables cost.** If `tbits = 20` (0.11 GiB) costs little, the epic is
unblocked cheaply. If it costs a lot, the web profile is a genuinely different
operating point and the epic needs to say so. Either way the number decides it,
and it is being measured rather than argued.

## F10 — M3 answered: the codec is compute-bound in the mixer, not memory-latency-bound

Measured on **dev-ai (aether): 64 cores, load 0.36, idle** — moved off
`arcana-devs`, which was at load 95 with four sibling agent sessions, because a
timing taken there is not a measurement. Every row pinned to the same 8-core set,
`dickens.2m`, byte-exact round-trip on every row.

| tbits | output bytes | ratio | vs native | enc s | dec s | enc peak RSS | dec peak RSS | RT |
|---|---|---|---|---|---|---|---|---|
| native (=24) | 461,437 | 0.220030 | — | 80.8 | 27.0 | 1.59 GiB | 1.47 GiB | PASS |
| 24 (control) | 461,437 | 0.220030 | **byte-identical** | 80.4 | 27.1 | 1.56 GiB | 1.47 GiB | PASS |
| 22 | 466,176 | 0.222290 | **+1.03%** | 74.2 | 25.0 | **0.55 GiB** | **0.40 GiB** | PASS |
| 20 | 476,746 | 0.227330 | **+3.32%** | 69.8 | 23.5 | **0.26 GiB** | **0.109 GiB** | PASS |
| 18 | 499,852 | 0.238348 | **+8.32%** | 56.6 | 19.2 | **0.197 GiB** | **0.0327 GiB** | PASS |
| **nocol** (L2, tables untouched) | 472,253 | 0.225188 | **+2.35%** | **26.9** | 26.0 | 1.57 GiB | 1.42 GiB | PASS |
| **nocol + tbits20** | 487,506 | 0.232461 | **+5.65%** | **23.1** | 22.5 | 0.266 GiB | 0.105 GiB | PASS |

### The two levers compose almost exactly, which makes the design space predictable

| config | encode speedup | output cost |
|---|---|---|
| `nocol` alone | **3.00×** | +2.35% |
| `tbits20` alone | 1.16× | +3.32% |
| both | **3.49×** | +5.65% |

Speedups multiply (3.00 × 1.16 = 3.48 predicted, **3.49 measured**) and costs add
(2.35 + 3.32 = 5.67 predicted, **5.65 measured**). They are independent knobs —
`nocol` removes redundant encoder passes, `tbits` shrinks the working set — so a
preset can be composed from them without re-measuring every combination.

Note what each buys that the other cannot: **`nocol` buys speed and no memory**
(RSS unchanged at 1.57/1.42 GiB); **`tbits` buys memory and little speed**
(1.16×). The memory result is the one that matters for the web codec — decode peak
falls **1.47 GiB → 0.109 GiB, a factor of 13.5**, for +3.32% output.

The `tbits24` row is a control: 2 MB derives `tbits = 24` anyway, so the cap must
be a no-op — and the output is byte-identical, which is what a working instrument
should say.

**The M3 verdict.** Member C's alternative hypothesis was that an 18 GB working set
makes essentially every probe an LLC/TLB miss, so the codec would be
memory-latency-bound and the whole engineering programme should be footprint. The
prediction that distinguishes it: shrink the working set and throughput should rise
roughly in proportion.

It does not. **A 2.9× smaller encode working set (1.59 → 0.55 GiB) buys 8%
throughput** (80.8 → 74.2 s), and 3.7× smaller on decode buys 8%. Memory latency is
therefore a *minor* term. The cost is compute in the mixer — 24 model lookups plus
two mixer layers plus an APM chain, per bit — exactly where F5's attribution put it.

Both candidate explanations for the flat per-type profile are now eliminated by
measurement: it is not the entropy coder (F5) and it is not memory latency (F10).

**And the memory trade is excellent on its own terms.** +1.03% output for ~3× less
memory, on both sides. That is not a painful trade-off; at `tbits = 22` the decoder
needs 0.40 GiB instead of 1.47 GiB on this file, and by the F1 scaling a ≥16 MB
file would need roughly 0.85 GiB instead of 13.50 GiB — which is the difference
between "impossible in a browser" and "ordinary". F9's blocker on the web-codec
epic looks cheap to lift, pending the `tbits = 20` and `18` rows.

## F11 — L1's test gate, and a pre-existing defect it exposed

`cargo test --release` on the L1 tree after the F8 fix: **305 passed, 6 failed**
(was 285/26). The remaining six are
`test_bwt_{rans,order2_rans,adaptive,ctxmix,geomix}_corpus_round_trip_all_files`
and `test_entropy_context2_corpus_round_trip_7_files`.

**They are not mine, and I checked rather than assumed.** I created a pristine
detached worktree at `origin/release/cubrim-1-0.3.x` (`09ef2bb`, the v0.3.2 tag
commit, no changes of any kind) and ran one of them there:

<!-- gate:literal -->
```
test result: FAILED. 0 passed; 1 failed; 0 ignored; 0 measured; 321 filtered out
assertion `left == right` failed: BwtRans corpus round-trip: 0/10 files tested
```
<!-- /gate:literal -->

Every skip line names the same cause: the fixtures live under
`documentation/ephemeral/research/corpus/*.bin`, and that directory **does not
exist in any checkout of this repository** — `ephemeral/` is not tracked. The
tests assert `10/10 files present and clean`, so absent fixtures fail rather than
skip.

So the honest accounting for L1 is: **26 failures → 6, and those 6 are the
environment baseline.**

**The pre-existing defect, reported not swept:** six tests on the shipped release
branch **cannot pass in a fresh clone**. A test that always fails wherever it has
not been hand-provisioned is a dead gate — it protects nothing and it trains
everyone to read a red suite as normal, which is exactly how the 26 real failures
above could have been dismissed. This is the same family as `cubrim-site` having
no test workflow (now `CUBR-0090`) and the untracked secret-scan hook (now
`SEC-0019`): a guard that is configured but not reachable. Needs its own ID and
either committed fixtures, a generator, or an honest `#[ignore]` with the reason.

## F12 — M1 closed with a direct number: the coder is **2.0%** of the per-bit budget

The consilium pre-registered this as the first measurement and attached a kill
rule: *stub the entropy coder, measure end-to-end; coder share < 25% ⇒ NEW-22 is
cancelled on the CM path, not descoped.*

I did not stub it. A null coder emits no bytes, which changes every downstream
competitive comparison and therefore measures a different encoder. Instead the
per-bit loop is timed in place — `predict_bit` + `update_bit` against
`RangeEncoder::encode` — which costs two `Instant::now()` per bit while enabled
and **emits byte-identical output**, so the split is measured on the real path.

`dickens.2m`, dev-ai, three CM2 passes in one encode (base + two column
variants):

<!-- gate:literal -->
```
CM2-BIT-SPLIT bytes=2097152 model_s=24.182 coder_s=0.514 coder_share=2.08%
CM2-BIT-SPLIT bytes=2097152 model_s=25.132 coder_s=0.516 coder_share=2.01%
CM2-BIT-SPLIT bytes=2097152 model_s=25.204 coder_s=0.517 coder_share=2.01%
```
<!-- /gate:literal -->

**Coder share 2.0%**, an order of magnitude below the kill threshold. By Amdahl an
infinitely fast entropy coder yields **1.02×** end-to-end. NEW-22's recorded
target — decode ≥500 MB/s — was unreachable by a factor of thousands on this path,
and the consilium was right to insist the target be restated end-to-end before any
work started.

Model 24.2 s against coder 0.51 s also states the positive finding precisely: the
cost is the **model** — 24 hash-indexed table lookups, two mixer layers and an APM
chain, per bit. That is where any future throughput work has to go.

## F13 — the wire-format exponent (NEW-27) is implemented, and its compatibility is one-directional

Implemented in the CM2 length header, bits 56..60, `0` = derive as before.
Verified by running, not by argument:

| property | result |
|---|---|
| capped archive (`tbits=18`) decodes on a decoder given **no configuration** | **PASS** |
| uncapped output byte-identical to the pre-change build | **PASS** — sha `2840d51a…` both |
| pre-change decoder reads new **uncapped** output | **PASS** |
| pre-change decoder reads a **capped** archive | **fails closed**, see below |
| `--preset web` on `dickens.2m` | 487,506 B, encode peak **0.26 GiB**, round-trip PASS |

**I documented this wrong first and am correcting it.** I wrote that `web`
archives "remain mutually decodable with every other preset". They do not: a
decoder that predates the field cannot read a capped archive. What it does
instead is the part that matters, and it was verified rather than assumed —

<!-- gate:literal -->
```
Error: DecodeError: MODE_CM2: coded stream exhausted before orig_len bytes decoded
exit=2, no output file written
```
<!-- /gate:literal -->

— it **fails closed**. No silent corruption, no partial file. The QA-F guards on
the release branch catch it, which is a good argument for CUBR-0089 landing them
on `main`.

So the honest statement, now in the code docs and the CLI help: `max` and
`balanced` archives decode **everywhere including older builds**, because they
leave the field zero; `web` archives need a decoder that reads the field.
Choosing `web` is a decision about who can open the result.

## F14 — the preset trade is class-dependent, and `balanced` is a no-op on executables

`ooffice.2m` (exe), same host and pin:

| config | output | vs native | enc s | dec peak RSS |
|---|---|---|---|---|
| native | 677,605 | — | 93.9 | 1.56 GiB |
| tbits22 | 685,459 | +1.16% | 89.7 | 0.40 GiB |
| tbits20 | 704,087 | +3.91% | 87.8 | **0.107 GiB** |
| tbits18 | 738,469 | +8.98% | 78.6 | 0.033 GiB |
| **nocol** | **677,605** | **byte-identical** | 94.0 | 1.56 GiB |
| nocol+tbits20 | 704,087 | +3.91% | 87.4 | 0.107 GiB |

`nocol` produces the **byte-identical blob** and no speedup — exactly as predicted
for a class where a type transform wins and the CM2 column sweep never fires.
Predicted before the run and confirmed by it, which is the only reason the
prediction is worth anything.

Two consequences for how presets get published:

- **`balanced`'s 3.00× is a text/xml/database number, not a corpus number.** Any
  public claim must say which classes it applies to, or it is misleading on
  exactly the half of the corpus where Cubrim's competitors are strongest.
- **The memory lever is class-independent.** Decode peak lands at 0.107–0.109 GiB
  at `tbits=20` on both `dickens` and `ooffice`, because decode is CM2 alone
  whatever won at encode time. That is the number the web-codec epic needs, and it
  does not vary by input type.

## F15 — L3 was attempted and abandoned rather than reported

The harness exists (`l3.sh`: `ooffice.2m` at `CUBR_THREADS` ∈ {default, 64, 16,
8, 4}, deliberately unpinned because the question is whole-machine behaviour and
pinning to 8 cores while varying thread count conflates the two). It waited for a
quiet host, started at load 1.42, and I killed it before it produced a single
complete row.

**Why.** The benchmark track had begun its competitor baseline on the same
machine. Load was only 6.80 on 64 cores, so on a naive reading there was ample
headroom — but the contention was **unequal across the rows**: a single-threaded
`brotli -q 11` steals ~1/64 of capacity from the 64-thread row and essentially
nothing from the 4-thread row. That biases the comparison **in favour of capping
threads**, which is my own hypothesis.

This is the same error I refused earlier when I declined to run the sweep under
falling background load with the full-footprint row first, and the same standard I
imposed on three sibling sessions. Applying it to someone else's numbers and not
to my own would make it a rhetorical device rather than a standard.

The other host was not an alternative: `arcana-devs` was at load 8.09 on 16 cores
with a cubrim process from another session still running.

**So L3 has no number, and the honest report is that it has no number.** The
script is in place and takes one command on a genuinely quiet host. What is
recorded stays what was observed in F6 — two concurrent encodes drove a 16-core
box to load 82, and the mechanism (per-level `available_parallelism()` multiplying
through nested candidates rather than sharing a budget) is read from source. That
is a *defect description*, not a measured lever, and it is not to be quoted as one.

## Measurement conditions — what these numbers are and are not

I told the sibling sessions that a timing taken on a contended host is not a
measurement. The same standard applies to mine, so here is the exact status of
every number in this document.

**Exact and load-independent** — all sizes, all sha256 values, all round-trip
results, and the source-derived table-footprint arithmetic in F1. These do not
move with host load and are quotable as they stand.

**Same-process ratios, taken under moderate load** — the attribution shares
(`cm2` 98.8%, `base` 43.5%, and so on) and the CM2 variant multipliers (2.27×,
3.30×). These compare two phases *inside one encode on one host*, which is the
most load-robust form of timing comparison available: both phases see the same
contention, so the ratio survives what an absolute figure would not. The
attribution runs happened at load ~6–15, not the 80+ the box reached later.
They are good enough to rank cost centres and to kill NEW-22 — a lever competing
for 98.8% of a profile is not saved by a factor-of-two timing error — and they
are **not** good enough to publish as throughput.

**Absolute wall-clock figures in the F5 table** (140.0 s, 207.1 s, …) are
recorded for provenance, not quoted as throughput anywhere, and none of them has
been written to the DB.

**Not taken at all** — the table-size sweep. It is armed behind a quiet-host gate
and will report nothing rather than something wrong. Consequence: the derived
claim that the 2.27–3.30× translates into an end-to-end corpus speedup is
**unmeasured**, and `--preset balanced` therefore ships with slice numbers only.

One gap in the gate itself, found and recorded rather than quietly patched: the
quiet-sweep script's `busy()` check tests `pgrep -x cubrim`, which does not match
the renamed binary copies the identity gates run (`cubrim-sweep`, `cubrim-l1v2`).
Its load-average check catches those anyway, so the gate has not admitted a bad
row — but the process check alone would not have stopped one.

## Status of the pre-registered measurements

| ID | question | state |
|---|---|---|
| M1 | null-coder ablation; kill rule: coder share < 25% ⇒ NEW-22 cancelled on the CM path | **superseded in part.** The coder cannot exceed CM2's 98.8%, and F1/M3 test the same question from the footprint side with a cheaper instrument. Ablation still to run to put a number on the coder itself. |
| M2 | encode/decode asymmetry attribution | **ANSWERED — F2.** Internal CM2 variant sweep, not the outer rail. Kill rule on the outer rail: disabling it cannot cost ratio because it never wins, and it cannot buy speed because it is already hidden. |
| M3 | memory-bound vs compute-bound | sweep built and pending a quiet host; F1 gives the footprint arithmetic it tests |
| M4 | the `code` 0.0850 outlier | reframed by F3 into a per-scope attribution run |

Held back deliberately: the sweep was **not** started while the attribution loop
still had the CPU. Running it under falling background load, with the
full-footprint row first, would have made every small-table row look faster for
a reason that has nothing to do with the tables — manufacturing support for my
own hypothesis. The rows are pinned to one fixed core set, the pin is never
widened for a row, and no row is re-run to improve its number.
