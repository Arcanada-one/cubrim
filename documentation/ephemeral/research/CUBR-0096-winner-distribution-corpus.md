# CUBR-0096 — per-block value-stream winner distribution across the corpus

**Status: measurement, plus one decisive candidate run. Does NOT reopen the kill.**
Measured 2026-08-12 on `dev-ai`. Companion to
`CUBR-0096-inner-sticky-gate-result.md`, which killed the lever.

> **What this adds.** The gate result states that its corpus arm never ran and that
> "no statement is made about the remaining corpus files". This is that statement, for
> the one question the corpus can answer cheaply: **on how many blocks, and on which
> files, does the eight-way value-stream competition actually change its mind?**
>
> It also **corrects a claim the gate result inherits from F18**. F18 measured
> `geomix` winning 384/384 blocks on both `x-ray` and `ooffice` and concluded the
> competition "computes a constant". Both cells were 2 MB slices. At full-file scale
> `x-ray` holds, **`ooffice` does not**, and on `mozilla` — the largest executable in the
> corpus, 9384 competed blocks — **`geomix` is not even the plurality winner**.
>
> **Second pass (2026-08-12, same day):** the corpus is closed from 14 files to 24, and
> with the full table the question *why these files and not those* has a mechanical
> answer. It is neither class nor size: the competition runs **iff `MODE_MED16`'s raster
> detector fires**, and that detector — documented as skipping "text, exe, random" — in
> fact fires on two executables and two binary files, which carry **77.5% of all
> competition work in the corpus**. See § *The gate*.

## How this lane arrived here, in one paragraph

This is the "second lane" named in the gate result's § *Why this document exists*. It
read `origin/main`, found no sticky mechanism and no `FINAL:` counter, and rebuilt both
from the instrumentation step. The gate result landed mid-flight and stopped it. The
re-implementation is **not proposed for merging** — the lever is killed and a second
implementation of a killed lever is worth nothing. It is left at
`cubr-0096-sticky-vs` @ `ed8bc3f` as a pushed reference and nothing more. What survives
is the instrument and the measurement below, because both are absent from `main`.

## Instrument

`FINAL:<scheme>` counters in `prof.rs`, incremented once per block with the scheme that
won *that block* — as distinct from the pre-existing `win()` counter, which fires every
time a candidate becomes the running minimum and therefore counts several "wins" per
block. Active only under `CUBRIM_PROFILE=1`; it touches a counter map and never the
emitted bytes.

F18 built this counter on a branch that predates the candidates-array refactor. It is
ported here onto current `main`, where a BWT-family candidate may decline (`None`) and is
then never scored. Ported, not copied — the old if-chain shape no longer exists.

**Validation against a known result:** re-running F18's exact cell (2 MB `x-ray` slice)
reproduces `FINAL:geomix = 384`, no other `FINAL:` row. 384/384, as F18 reported.

### The slice control — why "slice artefact" and not "revision drift"

The correction below rests on comparing a slice figure from F18's revision against a
full-file figure from this one. That comparison has an alternative explanation which must
be excluded before the correction can stand: **the codebase changed in between**, and
today's encoder would disagree with F18 on the *slice* too. If that were so, the
difference would be revision drift and calling it a slice artefact would be wrong.

Run on the same binary, same revision, same instrument as every other row here:

| input | blocks | winners |
|---|---:|---|
| `ooffice`, first 2 MB | 384 | `geomix` 384 — **constant** |
| `ooffice`, full 6,152,192 B | 1128 | `geomix` 1000, `lz_rans` 128 |

**The slice reproduces F18 exactly on current code.** F18 was not wrong about what it
measured; its cell simply does not survive being scaled to the real file. The difference
is scale, and revision drift is excluded.

The slice is also byte-for-byte the artefact another lane already measured: it compresses
to **677,605 bytes**, the figure CUBR-0092 recorded for its L3 thread-cap experiment
("byte-identical on ALL FIVE rows"). So the slice construction and this binary both agree
with an independently recorded result, which is a stronger check on the instrument than
the `x-ray` validation alone.

## Results

Full files from the 24-file world corpus, `CUBRIM_PROFILE=1`, `CUBR_THREADS=64`, default
(`--max`) encoder.

| file | class | bytes | blocks competed | winner distribution | winner constant? |
|---|---|---:|---:|---|---|
| `x-ray` | image | 8,474,240 | 1560 | `geomix` 1560 | **yes** |
| `mr` | image | 9,970,564 | 1836 | `geomix` 1836 | **yes** |
| `ptt5` | image | 513,216 | 96 | `geomix` 81, `lz_rans` 15 | no — 15.6% |
| `ooffice` | exe | 6,152,192 | 1128 | `geomix` 1000, `lz_rans` 128 | no — 11.3% |
| `mozilla` | exe | 51,220,480 | 9384 | **`lz_rans` 5141, `geomix` 4215, `ctxmix` 28** | **no — geomix loses** |
| `sao` | binary | 7,251,944 | 1332 | `geomix` 1331, `ctxmix` 1 | no — 0.08% |
| `kennedy.xls` | binary | 1,029,744 | 192 | `geomix` 129, `lz_rans` 63 | no — 32.8% |
| `samba` | exe | 21,606,400 | 0 | — | competition never runs |
| `osdb` | database | 10,085,684 | 0 | — | competition never runs |
| `nci` | database | 33,553,445 | *running* | *not yet measured* | *pending* |
| `webster` | text | 41,458,703 | *running* | *not yet measured* | *pending* |
| `enwik8` | text | 100,000,000 | *running* | *not yet measured* | *pending* |
| `dickens` | text | 10,192,446 | 0 | — | competition never runs |
| `reymont` | text | 6,627,202 | 0 | — | competition never runs |
| `xml` | xml | 5,345,280 | 0 | — | competition never runs |
| `plrabn12.txt` | text | 481,861 | 0 | — | competition never runs |
| `lcet10.txt` | text | 426,754 | 0 | — | competition never runs |
| `alice29.txt` | text | 152,089 | 0 | — | competition never runs |
| `asyoulik.txt` | text | 125,179 | 0 | — | competition never runs |
| `sum` | binary | 38,240 | 0 | — | competition never runs |
| `cp.html` | text | 24,603 | 0 | — | competition never runs |
| `fields.c` | code | 11,150 | 0 | — | competition never runs |
| `xargs.1` | text | 4,227 | 0 | — | competition never runs |
| `grammar.lsp` | code | 3,721 | 0 | — | competition never runs |

**All 24 corpus files, sorted by competed blocks then size.** The first version of
this document measured 14 and listed the ten it had not reached; this scan closes that
gap. Seven files compete; fourteen are measured at zero; **three rows (`nci`, `webster`,
`enwik8`) are still encoding at the time of this commit and are marked pending rather
than assumed.** They are predicted zero (see § *The gate*), and a prediction is not a
measurement — this commit is pushed early because the fleet was killed twice tonight,
not because those three are finished.

Every row above is a **completed** encode (`exit 0`). This matters more than it looks:
a still-running encode has an empty `FINAL:` section that is textually identical to
"the competition never runs here". `osdb` was read mid-run during this scan and briefly
looked like a zero row; it is listed as one only because its exit code was checked
afterwards. Any future reader of these logs should check the `.done` file, not the
absence of rows.

Counts are exact and load-independent: the encode is deterministic, so the winner of each
block is a property of the input, not of how busy the host was.

**No timing figure is reported from this scan.** The runs shared the host with builds and
with each other, so the wall and CPU columns collected alongside are contaminated. They
are deliberately omitted rather than quoted with a caveat. The one timing pair that *is*
quoted in this document comes from the paired `ooffice` run below, whose two arms ran
back to back on the same host at the same thread count.

## The gate — *which* files compete is decided by MODE_MED16's raster detector

The first version of this document could only tabulate which files compete. With the
corpus closed, the question "why these and not those" has a single answer, and it is
neither the data class nor the file size.

**The competition runs if and only if `MODE_MED16` reaches its nested encode.**

`encode_rans_family_value_stream` — the eight-way competition, and the only place the
`FINAL:` counter fires — is reached only when `config.value_scheme` is a rANS-family
member. The default is `BitpackFixed`, and the encoder contains exactly one non-test
assignment of a rANS-family scheme: `codec.rs:2830`, inside `encode_med16`, which sets
`nested_config.value_scheme = ValueScheme::BwtRans` before encoding its residual. Every
competed block in this corpus is a block of a MED16 residual.

Two guards stand in front of it, and they carve the corpus into three tiers:

| tier | condition | `med16` prof row | competes | files |
|---|---|---|---|---|
| 1 | input ≤ 65,536 B | **absent** | no | `grammar.lsp`, `xargs.1`, `fields.c`, `cp.html`, `sum` |
| 2 | larger, raster detector declines | calls=1, wall ≈ 0.01–0.03 s | no | `asyoulik.txt`, `alice29.txt`, `lcet10.txt`, `plrabn12.txt`, `xml`, `reymont`, `dickens`, `osdb`, `samba` |
| 3 | raster detector fires | calls=1, wall 8.5–242.7 s | **yes** | `ptt5`, `kennedy.xls`, `ooffice`, `sao`, `x-ray`, `mr`, `mozilla` |

**Tier 1** is the caller-side guard at `codec.rs:391`, `if data.len() >
config.cube_size_limit()`, which encloses the whole type-gated heavy-transform block
(binfloat, med16, bcj, soa, geocm). `cube_size_limit()` is `b*b` with `B_DEFAULT = 256`,
so the threshold is **65,536 bytes**. Below it the block is never entered, `prof::track`
never runs, and no `med16` row is written at all. (`encode_med16` repeats the same check
at its own head, but that copy is not what produces the observed absence — `track` wraps
the call unconditionally, so it would still emit a row reading calls=1.)

**Tier 2 vs tier 3** is `med16_detect_width`, a raster-periodicity test whose own comment
reads: *"a real 2-D raster has a SHARP vertical-period dip … Non-image input (text, exe,
random) has a flat cost curve, so we skip it here"*. When it declines, `encode_med16`
returns `None` immediately and the file costs ~0.02 s of detection.

The tiers are not fitted to the outcome — they are separated by a column, and the
separation is absolute. Tier 2 spends at most **0.033 s** in `med16`; tier 3 spends at
least **8.502 s**. That is a factor of 258 with nothing in the gap.

### Size is not the gate, and the corpus contains the controlled pair that proves it

`osdb` is 10,085,684 B and competes **0** blocks. `mr` is 9,970,564 B and competes
**1836**. They differ by 1.2% in size and completely in outcome. `samba` (21,606,400 B,
zero) is more than three times the size of `ooffice` (6,152,192 B, 1128). `ptt5` competes
at 513,216 B while `plrabn12.txt` at 481,861 B does not. Above the 64 KiB floor, size
predicts nothing.

### The detector's documented selectivity is wrong, and that is where the work goes

The comment says the detector skips text, exe and random input. Measured, it fires on
`ooffice` and `mozilla` (exe) and on `sao` and `kennedy.xls` (binary): **four of the seven
competing files are not images**, and they carry 12,036 of the 15,528 competed blocks —
**77.5% of all value-stream competition in the corpus happens on input the gate was
written to skip.**

This is the mechanical reason the per-file discipline in point 2 below is not pedantry.
Class is the wrong unit because the gate never looks at class; it looks for vertical
periodicity in the bytes, and it finds it in some executables and some spreadsheets and
not in others. `exe` splits (`ooffice`, `mozilla` compete; `samba` does not) exactly as
`binary` splits (`sao`, `kennedy.xls` compete; `sum` does not).

### A second file where the competition is provably discarded

The `ooffice` resolution below shows 1128 competitions whose result never reaches the
output. `ptt5` is a cleaner instance of the same waste and it was already in the first
scan, unnoticed: its `med16` row reads **wins=0**, meaning MED16's output never once
became the running minimum at the outer competition, yet its nested encode ran **96**
value-stream competitions. `prof::win` is incremented only when a candidate becomes the
running best (`codec.rs:443`), so wins=0 is a direct read that every one of those 96 was
thrown away. On `ooffice` the discard had to be established from the emitted mode byte;
on `ptt5` the counter says it outright.

## What this corrects

**1. "The competition computes a constant" is a slice artefact, and on the largest
executable it is not merely non-constant — `geomix` loses.**

F18 measured 384/384 on a 2 MB `ooffice` slice — and so does this revision, per the slice
control above, so the disagreement is scale rather than drift. The full 6,152,192-byte
file competes 1128 blocks and `lz_rans` takes 128 of them. The gate result carries the slice claim
forward when it explains its identical-bytes cell as "consistent with F18's finding that
the competition computes a constant where it runs". That explanation does not hold for
`ooffice`.

`mozilla` — 51,220,480 bytes, the largest executable in the corpus and 9384 competed
blocks — is the sharper case. Three schemes take real shares, and the plurality winner is
**`lz_rans` with 5141 blocks (54.8%) against `geomix`'s 4215 (44.9%)**. On this file the
premise is not just "the constant is sometimes wrong"; the scheme the whole lever was
designed to pin to is **not the one that usually wins**. A sticky rule anchored on early
blocks would be pinning to a minority scheme across half the file.

This is the same failure mode F19 recorded and forbade — a 2 MB slice giving a number the
full file contradicts — recurring on a different quantity. F19 caught it on ratio; it also
applies to *which scheme wins*. Note the direction of the error scales with file size:
`x-ray` and `mr` (8.5 and 10 MB) are constant, `ooffice` (6 MB) is 11% divergent, and
`mozilla` (51 MB) inverts. Slices were never going to show this.

**2. Constancy is a per-file property, not a per-class one.** `x-ray` and `mr` are
constant; `ptt5` is not, and all three are `image`. Any future lever that assumes "image
⇒ constant winner" is assuming something false.

**3. The mechanism's observable scope is wider than image and exe.** F18 and the
CUBR-0096 brief both scope the mechanism to image and exe. `sao` and `kennedy.xls` are
`binary`, and both reach the competition — 1332 and 192 blocks. The `binary` class belongs
in the scope statement.

**4. Where the competition does not run at all, it is not a small effect — it is zero
blocks.** Fourteen of the twenty-one files measured so far never reach the competition
(three rows still pending). For those, no value-stream lever of any design can save
anything, because there is nothing to save. **The corpus-wide shape is now known: the
value-stream competition is a minority path.** At most seven of 24 files reach it, and
the entire lever — the one the gate killed — could only ever have applied to those seven.

**5. The per-file discipline in point 2 cuts both ways — including in this document.**
Point 2 says constancy is a per-file property, not a per-class one. The identical caution
applies to *competing at all*, and the table above is its own counterexample: `binary`
contains `sum` at **zero** blocks and also `sao` at **1332** and `kennedy.xls` at **192**.
A class does not compete or not-compete; files do.

This matters most for `database`, where the evidence was **n = 1** — `osdb` never competes
and `nci` had never been measured. It is tempting to write "database never reaches the
competition", and earlier drafts of the surrounding bookkeeping did exactly that. Read the
zero rows as **specific named files**, never as classes.

**Update from the completing scan.** The caution was the right one to have written, and
the closing corpus vindicates it on a class the earlier draft did *not* flag: `samba` is
`exe`, 21,606,400 B, and competes **zero** blocks — while `ooffice` and `mozilla`, the two
other `exe` files, compete 1128 and 9384. So `exe` splits exactly as `binary` splits, and
a reader of the first table who had generalised "exe competes" from n = 2 would have been
wrong. Two of the four classes that looked homogeneous are not.

The `database` question itself is being answered by measurement rather than left at n = 1:
`nci` is encoding as this is written and its row is marked pending above. It is predicted
to land in tier 2 — above the 64 KiB floor, no raster periodicity — but that prediction is
recorded here precisely so it can be checked against the row when it lands, not so it can
substitute for it.

The temptation is worth naming because it is asymmetric: a *positive* result ("this file
competes 1128 times") is self-evidently about one file, while a *negative* one ("zero
blocks") reads like a property of the kind of data. It is not.

## What this does NOT do

- **It does not reopen the kill.** The gate fired on end-to-end speedup (1.33× / 1.05×
  against a 1.50× bar) with an oracle ceiling of ~1.37× / ~1.06×. That arithmetic is
  independent of how often the winner changes, and nothing here moves it.
- **It does not establish requirement 4** (≤ +0.50% corpus ratio cost). One candidate arm
  now exists — `ooffice`, measured below at **exactly zero** cost — but requirement 4 is a
  *corpus* figure and one file is not a corpus. What the table bounds is where a ratio cost
  could come from at all: only the seven files that compete, and on `x-ray` and `mr` a
  sticky choice costs zero because there is only ever one winner to be sticky about.
- It now measures **21 of the 24 corpus files**, with `nci`, `webster` and `enwik8` still
  encoding at the time of this commit and marked pending in the table. The first version
  of this document measured 14; the seven added are `asyoulik.txt`, `lcet10.txt`,
  `plrabn12.txt`, `xml`, `reymont`, `dickens` and `samba`, all at zero competed blocks.
- **Requirement 4 is still not established and this scan does not attempt it.** Knowing
  which files compete bounds where a ratio cost could come from — at most seven files —
  but it measures no candidate arm and produces no ratio figure.

## The open question, RESOLVED — the winner never reaches the output on `ooffice`

The first version of this document left a tension on the record: the gate result measured
**byte-identical** `ooffice` output between its baseline and its sticky candidate, yet this
scan shows 128 of 1128 blocks where `lz_rans` beats `geomix`. Two explanations were offered
and neither was verified. It is now measured, because it needed one run rather than a
campaign.

**Test.** Encode `ooffice` twice on the same host, `CUBR_THREADS=64`, binaries pinned by
hash — baseline `sha256:e2917ca1…` (full competition) against candidate
`sha256:19ebfe14…` run with `--sticky-window 1`, which competes only the anchor of each
chunked container and forces every other block to that anchor's winner. If the 128
`lz_rans` choices reach the output, overriding them must change bytes.

**Result.**

| arm | sha256 of output | bytes | round-trip |
|---|---|---:|---|
| baseline `--max` | `f4709c0a8eb6a787b577c0c5865ff654d30d6c6acfc2b12c67681c7f6a0a0be6` | 1,763,460 | PASS |
| `--sticky-window 1` | `f4709c0a8eb6a787b577c0c5865ff654d30d6c6acfc2b12c67681c7f6a0a0be6` | 1,763,460 | PASS |

**Byte-identical.** Both arms decode back to the original `ooffice`
(`sha256:e7ee0138…`, 6,152,192 bytes) exactly. The candidate's own counters confirm the
mechanism fired rather than silently no-opping: `STICKY:reused = 1104`, `FINAL:geomix = 24`
— 1104 of 1128 blocks were forced, 24 remained anchors, and no forced scheme declined.

**Hypothesis 2 is confirmed and hypothesis 1 is not needed.** On `ooffice` the per-block
value-stream winner does not reach the output at all. The container those blocks belong to
loses the *outer* competition and is discarded whole, so which scheme won inside it is
invisible in the emitted bytes.

That last sentence is **read off the artefact, not inferred from it**. The emitted
container's mode byte (offset 5, after `[MAGIC 4B][VERSION 1B]`) is **8 = `MODE_BCJ`** on
both arms — not `MODE_MED16` (7) and not `MODE_CHUNKED` (2). The `med16` → nested chunked
`base` path that ran all 1128 value-stream competitions is therefore absent from the
output. An earlier draft of this document asserted the discard while citing only evidence
*consistent* with it (`bcj_cm2`, `cm2`, `med16` and `base` all taking outer wins, which
does not by itself say which one was emitted); the mode byte settles it.

This **corrects the gate result's explanation without touching its verdict.** The gate
explained its identical-bytes cell as "consistent with F18's finding that the competition
computes a constant where it runs". That is not why: the winner is *not* constant on
`ooffice` (1000/128). The bytes are identical because the work is thrown away.

That is a **stronger** statement about the waste than "it recomputes a constant". On this
file the eight-way competition is not merely rediscovering a known answer — it is computing
an answer that nothing reads.

### And the kill is robust to scoping

The gate's candidate scoped sticky to `MED16` as its only authorized caller and measured
**1.05×** on `ooffice`. This candidate forces at *every* chunked caller — a strictly wider
attack on the same waste — and measures **168.77 s → 143.64 s, 1.175×**.

Both arms here are same-host, same-thread-count, single-run each, so 1.175× is internally
valid but is **not** a repeatability estimate and is **not** comparable to the gate's
figure in absolute terms (that ran pinned to CPUs 0-15 at `CUBR_THREADS=16`).

The point is the direction, not the decimal: widening the scope from MED16-only to every
caller still lands far below the **1.50×** bar. The kill was not an artefact of the gate
candidate's narrow scoping — a second, independently written implementation with a wider
reach fails the same gate. **The verdict stands, now from two implementations.**

What remains genuinely un-refuted is what the gate result already named: a mechanism that
removes the losers *without probing*, or one that makes the winner itself cheaper.

### The obvious next lever from here is already refuted — do not re-derive it

The discard makes a larger prize look available: `med16` costs 53.39 s of `ooffice`'s
169.16 s encode wall, and every second of it is spent on a container that is thrown away.
Abandoning that candidate earlier would be **byte-exact**, unlike sticky selection.

**F17 already measured this and it does not work.** Branch-and-bound on the deferred base
moved its share 73.52% → 71.84% — essentially unchanged — because `base` *wins* the inner
competition as `med16`'s nested encoder, so the bound never fires on it. The outer
container losing and the inner candidate winning are not in tension: they are different
competitions, and only the inner one is what the bound can see.

So the shape of the waste is now fully characterised — the work is discarded, and the
existing bound cannot stop it — and neither of the two obvious attacks (sticky selection;
branch-and-bound) is available. Any future proposal here has to be a third thing, and
should state up front why it is not one of these two wearing a different name. Recorded
this explicitly because this lane has already paid once for re-deriving a settled negative.

## Provenance

- Instrument: this branch, `code/cubrim-rs/src/prof.rs` + `src/codec.rs` (`FINAL:` rows).
- Raw logs: `dev-ai:/root/cubr0096/winners/*.log`, one per file, each containing the full
  candidate-attribution table as emitted.
- Scan driver: `dev-ai:/root/cubr0096/winner-scan.sh`.
- **Completing scan (the ten remaining files):** driver
  `dev-ai:/root/cubr0096/winner-scan-2.sh`, logs `dev-ai:/root/cubr0096/winners2/*.log`,
  same method and same `CUBR_THREADS=64`.
- **Binary continuity for the completing scan.** The first scan's binary was overwritten
  when the decide-run binaries were built at 04:26. The completing scan pins
  `dev-ai:/root/cubr0096/cubrim-baseline`, sha256 `e2917ca1…`, and the driver refuses to
  run on a hash mismatch (`winners2/BINARY_SHA256` records what it ran). That binary is
  *proven* instrument-equivalent to the first scan rather than assumed to be: on `ooffice`
  it emits `FINAL:geomix 1000` / `FINAL:lz_rans 128` (`decide/base.log`), reproducing the
  first scan's `ooffice` row exactly. The two scans are therefore one dataset.
- **Predictions, written before the results they predict.**
  `winners2/PREREGISTERED-PREDICTION.md` (06:55, 3 of 10 rows done) predicted that large
  text *would* compete, on a file-size theory. `xml` refuted it.
  `winners2/PREDICTION-REVISED.md` (06:59, 4 of 10 done) withdrew that, derived the
  three-tier MED16 gate from source, and predicted zero for all six files then still
  running, flagging `samba` as the case most likely to break it. `samba` came back zero.
  `winners2/CORRECTION-1.md` (07:04, 5 of 10 done) fixed the line number attributed to the
  tier-1 guard. The `.done` mtimes date every row against these files. The first
  prediction is kept, wrong, rather than quietly deleted.
- Superseded re-implementation: `cubr-0096-sticky-vs` @ `ed8bc3f` — built, 12 tests green
  including a control proving `recheck=1` reproduces competitive output byte-for-byte.
  Not for merge. It is, however, the binary that produced the `ooffice` resolution above.
- `ooffice` decision run: `dev-ai:/root/cubr0096/decide/` — `hashes.txt`, `base.log`,
  `sticky.log`; driver `dev-ai:/root/cubr0096/ooffice-decide.sh`. Binaries pinned by
  sha256 in the section above and kept at `dev-ai:/root/cubr0096/cubrim-{baseline,sticky}`.
