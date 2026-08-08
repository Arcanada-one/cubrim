# The levers on the record: stand wall-clock 1.33×/1.16×/1.31× decode — smaller than the cycle ratios, and that is reported, not reconciled

**Measured:** 2026-08-08 04:19–05:07 UTC on the quiet stand (`dev-ai`,
AMD EPYC 7502P). **DB record:** `codec_revisions` id **8** (main `49e429e`,
built on the stand), hypothesis **NEW-30** (`measured`), `measurements`
rows for both revisions. `evaluation` untouched at 0. Raw journal:
[`CUBR-LEVERS-STAND-20260808/`](CUBR-LEVERS-STAND-20260808/) (TSV + log +
the exact runner script).

## Protocol — the campaign's own, exactly

- **Built from `main` `49e429e` on the stand** (fresh clone; binary sha256
  `12eaff4d…5830c`, rustc 1.96.1; `cm2.rs`/`codec.rs` SHAs recorded in the
  revision row) versus the resident rev-7 L1v2 binary (sha re-verified
  `534d3553…92c9f`). Not a copied DEVS binary.
- **Pin 0-15, `CUBR_THREADS=RAYON=OMP=4`** (meta-35 thread semantics), one
  warmup + **median of three** measured samples, GNU time wall + peak RSS,
  builds interleaved within every sample round, `cmp` round-trip after
  **every** decode — 18/18 PASS.
- **Slices sha-verified** (dickens.2m `df925056…`, nci.2m `6788fcc1…`,
  ooffice.2m `5041e86f…`). Cross-build archives **byte-identical** on all
  three files, and their SHAs equal the programme's canonical values
  (dickens `c8aed8ae…` = the F7 identity-gate value; nci `1dcc11fa…` = the
  STICKY12/DECODESPREAD archive; ooffice `4d563b48…`) — cross-build,
  cross-host, cross-week identity.
- **Admission and contamination:** admission loadavg 1.40 < 2.0 with a
  process snapshot recorded; post-run 1-min load 2.05 is the run's own
  decay (a 110 s threads-4 encode ended a minute before the snapshot) —
  the pre/post snapshots show the identical set of light resident daemons
  (total CPU delta < 0.05 cores over 48 minutes) and nothing new; per-cell
  sample spread ≤ 0.7%. The run is clean, and the evidence for that is in
  the log, not asserted.

## Results (medians of 3; seconds; RSS KiB)

| file | build | enc s | dec s | enc RSS | dec RSS |
|---|---|---:|---:|---:|---:|
| dickens | L1v2 (rev 7) | 78.45 | 26.43 | 1,631,360 | 1,543,680 |
| dickens | **49e429e (rev 8)** | **59.57** | **19.91** | 1,812,908 | 1,719,808 |
| nci | L1v2 | 116.74 | 18.05 | 1,721,868 | 1,429,504 |
| nci | **49e429e** | **111.25** | **15.62** | 1,863,676 | 1,709,568 |
| ooffice | L1v2 | 122.00 | 25.02 | 1,858,580 | 1,634,816 |
| ooffice | **49e429e** | **110.87** | **19.06** | 1,938,700 | 1,707,520 |

**Wall-clock speedups:** decode **1.328× / 1.156× / 1.313×**
(dickens / nci / ooffice); encode **1.317× / 1.049× / 1.100×**. Density
unchanged — identical archives, identical bytes.

## The two findings, stated plainly

1. **The stand wall-clock decode gains are materially smaller than the
   DEVS cycle-counter ratios** (dickens 1.33× vs 1.52×; nci 1.16× vs
   1.41×). Not reconciled away: different silicon (EPYC 7502P Zen 2 vs
   i9-9900K — different divider latency and cache hierarchy, which is
   exactly what both levers act on), wall clock includes constant
   startup/IO the cycle A/B excluded, and cycle counters are not wall
   clock. The stand numbers are the record; the DEVS ratios remain what
   they always were — pinned relative counters.
2. **The new build's decode peak RSS is ~11% higher** (dickens 1,543,680 →
   1,719,808 KiB). Cause read from the code, not guessed: the packed
   record's non-zero initializer (`vec![(PSCALE/2)<<16; n]`) commits every
   table page up front, while the old layout's zero-filled `c`/`st` arrays
   came from `alloc_zeroed` and stayed lazily allocated until touched. A
   real trade, recorded in NEW-30; a zero-representation offset (store
   `t − PSCALE/2` biased) is the obvious later fix if the memory matters —
   a candidate, not a commitment.

## What entered the record

- `codec_revisions` **8**: the 49e429e stand build with full provenance.
- `hypotheses` **NEW-30**: both levers, mechanism + measurement + both
  findings, `measured=true`, `measure_date` and `measure_task` set — the
  three NEW-28 integrity signals present from birth.
- `measurements`: 6 rows (3 files × revs 7 and 8), run_mode
  `levers-wall-pin0-15-t4`, `cpu_pin 0-15`, every row `rt_ok`. Cells not
  measured (other files, other presets, corpus-level anything) are simply
  absent — never estimated, never carried from DEVS.
- `evaluation`: **0**, untouched — nothing here passes a reopen gate.

## The standing dual verdict, quoted whole

**Archival: worth pursuing** — two levers now on the wall-clock record at
1.16–1.33× decode, byte-identical density. **Web: unreachable on this
algorithm** — the density WIN `0.877644` is a property of exactly the model
the web gate cannot afford; these are archival numbers and must never be
quoted against the web gate.
