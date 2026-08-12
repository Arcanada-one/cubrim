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

## Results

Full files from the 24-file world corpus, `CUBRIM_PROFILE=1`, `CUBR_THREADS=64`, default
(`--max`) encoder.

| file | class | blocks competed | winner distribution | winner constant? |
|---|---|---:|---|---|
| `x-ray` | image | 1560 | `geomix` 1560 | **yes** |
| `mr` | image | 1836 | `geomix` 1836 | **yes** |
| `ptt5` | image | 96 | `geomix` 81, `lz_rans` 15 | no — 15.6% |
| `ooffice` | exe | 1128 | `geomix` 1000, `lz_rans` 128 | no — 11.3% |
| `mozilla` | exe | 9384 | **`lz_rans` 5141, `geomix` 4215, `ctxmix` 28** | **no — geomix loses** |
| `sao` | binary | 1332 | `geomix` 1331, `ctxmix` 1 | no — 0.08% |
| `kennedy.xls` | binary | 192 | `geomix` 129, `lz_rans` 63 | no — 32.8% |
| `osdb` | database | 0 | — | competition never runs |
| `sum` | binary | 0 | — | competition never runs |
| `alice29.txt` | text | 0 | — | competition never runs |
| `cp.html` | text | 0 | — | competition never runs |
| `xargs.1` | text | 0 | — | competition never runs |
| `fields.c` | code | 0 | — | competition never runs |
| `grammar.lsp` | code | 0 | — | competition never runs |

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

## What this corrects

**1. "The competition computes a constant" is a slice artefact, and on the largest
executable it is not merely non-constant — `geomix` loses.**

F18 measured 384/384 on a 2 MB `ooffice` slice. The full 6,152,192-byte file competes
1128 blocks and `lz_rans` takes 128 of them. The gate result carries the slice claim
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
blocks.** Seven of the fourteen files measured never reach the competition. For those, no
value-stream lever of any design can save anything, because there is nothing to save.

## What this does NOT do

- **It does not reopen the kill.** The gate fired on end-to-end speedup (1.33× / 1.05×
  against a 1.50× bar) with an oracle ceiling of ~1.37× / ~1.06×. That arithmetic is
  independent of how often the winner changes, and nothing here moves it.
- **It does not establish requirement 4** (≤ +0.50% corpus ratio cost). One candidate arm
  now exists — `ooffice`, measured below at **exactly zero** cost — but requirement 4 is a
  *corpus* figure and one file is not a corpus. What the table bounds is where a ratio cost
  could come from at all: only the seven files that compete, and on `x-ray` and `mr` a
  sticky choice costs zero because there is only ever one winner to be sticky about.
- It measures **14 of the 24 corpus files**. The ten not measured are `dickens`, `nci`,
  `reymont`, `samba`, `webster`, `xml`, `enwik8`, `asyoulik.txt`, `lcet10.txt` and
  `plrabn12.txt`.

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
- Superseded re-implementation: `cubr-0096-sticky-vs` @ `ed8bc3f` — built, 12 tests green
  including a control proving `recheck=1` reproduces competitive output byte-for-byte.
  Not for merge. It is, however, the binary that produced the `ooffice` resolution above.
- `ooffice` decision run: `dev-ai:/root/cubr0096/decide/` — `hashes.txt`, `base.log`,
  `sticky.log`; driver `dev-ai:/root/cubr0096/ooffice-decide.sh`. Binaries pinned by
  sha256 in the section above and kept at `dev-ai:/root/cubr0096/cubrim-{baseline,sticky}`.
