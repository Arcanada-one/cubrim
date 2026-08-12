# CUBR-0096 — per-block value-stream winner distribution across the corpus

**Status: measurement only. This does NOT reopen the sticky lever.**
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
> `x-ray` holds and **`ooffice` does not**.

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
are deliberately omitted rather than quoted with a caveat.

## What this corrects

**1. "The competition computes a constant" is a slice artefact on `ooffice`.**
F18 measured 384/384 on a 2 MB `ooffice` slice. The full 6,152,192-byte file competes
1128 blocks and `lz_rans` takes 128 of them. The gate result carries the slice claim
forward when it explains its identical-bytes cell as "consistent with F18's finding that
the competition computes a constant where it runs". That explanation does not hold for
`ooffice`: the winner there is not constant.

This is the same failure mode F19 recorded and forbade — a 2 MB slice giving a number the
full file contradicts — recurring on a different quantity. F19 caught it on ratio; it also
applies to *which scheme wins*.

**2. Constancy is a per-file property, not a per-class one.** `x-ray` and `mr` are
constant; `ptt5` is not, and all three are `image`. Any future lever that assumes "image
⇒ constant winner" is assuming something false.

**3. The mechanism's observable scope is wider than image and exe.** F18 and the
CUBR-0096 brief both scope the mechanism to image and exe. `sao` and `kennedy.xls` are
`binary`, and both reach the competition — 1332 and 192 blocks. The `binary` class belongs
in the scope statement.

**4. Where the competition does not run at all, it is not a small effect — it is zero
blocks.** Six of the twelve files measured never reach the competition. For those, no
value-stream lever of any design can save anything, because there is nothing to save.

## What this does NOT do

- **It does not reopen the kill.** The gate fired on end-to-end speedup (1.33× / 1.05×
  against a 1.50× bar) with an oracle ceiling of ~1.37× / ~1.06×. That arithmetic is
  independent of how often the winner changes, and nothing here moves it.
- **It does not establish requirement 4** (≤ +0.50% corpus ratio cost). That needs a
  candidate arm — an encode under sticky — and no such arm was run here. What the table
  gives is the *upper bound on where a ratio cost could come from at all*: only the six
  files that compete, and on `x-ray` and `mr` a sticky choice would cost exactly zero
  because there is only ever one winner to be sticky about.
- **It says nothing about `nci`, `dickens`, `webster`, `reymont`, `xml`, `samba`,
  `enwik8` or the remaining canterbury files.** They were not measured.
- **`mozilla` was started and did not finish inside this lane's window.** It is the one
  in-scope `exe` file missing from the table. Left running rather than reported: at the
  cut-off it had spent 4 CPU-hours at 11.4 GiB RSS and entered a serial phase. The
  `ooffice` row already carries the exe correction, so `mozilla` would add confirmation,
  not a new conclusion. Its log will appear at
  `dev-ai:/root/cubr0096/winners/exe.mozilla.log` — **check `exe.mozilla.done` before
  reading it**, per the note under the table.

## Open question left on the record

On `ooffice` the gate result measured **byte-identical** output between its baseline and
its sticky candidate, yet this scan shows 128 blocks where `lz_rans` beats `geomix`.
Sticky selection that re-pinned those blocks to `geomix` should have cost bytes there.

Both observations reproduce — this lane's independent `--max` run of `ooffice` produces
**1,763,460 bytes**, matching the gate result's baseline cell exactly — so this is a real
tension, not a discrepancy between runs. Two candidate explanations, neither verified:

1. The gate's `MED16_STICKY_PLAN` was scoped to MED16 as its only authorized caller, so
   blocks competing under a different caller would keep competing and keep their winner.
2. The blocks where `lz_rans` wins may sit inside a container that loses the outer
   competition and is discarded whole, in which case their value-stream winner never
   reaches the output. `ooffice`'s attribution shows `bcj_cm2`, `cm2`, `med16` and `base`
   all taking outer wins, which is consistent with this but does not establish it.

Resolving it needs one run, not a campaign: encode `ooffice` under the rescued candidate
and diff the per-block winners. Recorded rather than guessed at, so the next lane starts
from the question instead of rediscovering the tension.

## Provenance

- Instrument: this branch, `code/cubrim-rs/src/prof.rs` + `src/codec.rs` (`FINAL:` rows).
- Raw logs: `dev-ai:/root/cubr0096/winners/*.log`, one per file, each containing the full
  candidate-attribution table as emitted.
- Scan driver: `dev-ai:/root/cubr0096/winner-scan.sh`.
- Superseded re-implementation: `cubr-0096-sticky-vs` @ `ed8bc3f` — built, 12 tests green
  including a control proving `recheck=1` reproduces competitive output byte-for-byte.
  Not for merge.
