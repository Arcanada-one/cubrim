# CUBR-ZEROREP-INDEP-20260809 — independent second-host replication of the zero-representation matrix

Status: **result, replication.** No hypothesis row is opened or closed by this document, and no
database write was made — `web_benchmark_hypothesis_evaluation` stays at zero rows and NEW-30
remains owned by the programme session.

## Why this record exists

`CUBR-ZEROREP-MATRIX-20260809-results.md` scopes itself explicitly:

> This result covers only the eight preregistered `nci`, `dickens`, and `ooffice` file/preset cells
> on `dev-ai`, with CPUs 0-15 and four threads.

The measurement below was run independently on a second host on the same day and was never committed.
It supplies exactly the cross-host generality the stand result disclaims. Until now it existed only
outside the repository, on one machine's local disk, which is not a durable scientific record.

## Provenance

| Item | This run | Stand (G3) |
|------|----------|------------|
| Host | `arcana-devs`, 16 cores | `dev-ai`, 64 cores |
| CPU pin | 0-15 (unchanged) | 0-15 |
| Toolchain | cargo 1.97.1 | cargo 1.96.1 |
| Host condition | contended: load1 median 36.9, max 77.4 (`loadlog.txt`, 268 samples) | quiet, load1 1.29 |
| Window | 2026-08-09T12:36:29Z .. 15:29:50Z | see G3 record |

Sources measured — identical to the three commits recorded in the stand's `HASHES.tsv`:

- base (pre-PR41) `e70d1cdca6226e994c0393149e364f252f7c0a1f`
- current (packed Ctr) `49e429e58722f730c4f3cbb0a69731fec430bb56`
- candidate (zero-rep) `368bc17df4a6b2f91d5896c86d963eba7acfe256`

## Result 1 — compressor output is deterministic across hosts (new)

All 24 archives produced here are **byte-identical to the 24 archives committed by the stand**:
every digest in `CUBR-ZEROREP-INDEP-20260809/archives.sha256` matches the corresponding entry in
`CUBR-ZEROREP-MATRIX-G3-RESULTS-20260809/SHA256SUMS` — 24/24, across two hosts, two core counts and
two cargo versions.

Within this run, all three builds share one archive digest per cell in 8/8 cells. That is the
correctness invariant the lever depends on: zero-representation changes residency without changing a
single output byte.

The archives themselves are therefore **not duplicated into this directory** — they are already in
the repository under the G3 results directory and are bit-for-bit the same objects. `archives.sha256`
is the join key.

## Result 2 — peak decode RSS replicates within 1 MiB

Per-cell medians of 3 timed decodes per build reproduce the stand's medians. The largest deviation
across all 24 cell/build combinations is **896 KiB**; most are under 640 KiB. Peak decode RSS is a
deterministic property of binary and input, not of host or load.

Decision axes, regenerated from `results.tsv` by `analyze.py`
(`P = current − base`, `R = current − zero`, KiB, medians):

| cell | P | R | R/P | resid | RSS-axes | vs G3 |
|------|---|---|-----|-------|----------|-------|
| nci/balanced | 259,328 | 653,056 | 2.518 | −393,728 | PASS | agrees |
| nci/web | 4,480 | 19,456 | 4.343 | −14,976 | PASS | agrees |
| dickens/max | 176,000 | 564,480 | 3.207 | −388,480 | PASS | agrees |
| dickens/balanced | 168,064 | 518,912 | 3.088 | −350,848 | PASS | agrees |
| dickens/web | 3,328 | 8,448 | 2.538 | −5,120 | PASS | agrees |
| ooffice/max | 72,960 | 233,984 | 3.207 | −161,024 | PASS | agrees |
| ooffice/balanced | 72,960 | 233,984 | 3.207 | −161,024 | PASS | agrees |
| ooffice/web | 2,432 | 6,912 | 2.842 | −4,480 | PASS | agrees |

8/8 PASS, 8/8 agreeing with the stand.

## Result 3 — the below-baseline RSS is lazy pages, confirmed per cell

Mechanism: PR #41's packed Ctr initialises every slot to the non-zero word `0x08000000`, physically
committing all table pages. The zero-representation XOR-bias makes the stationary word `0x00000000`,
so `calloc`'d pages stay lazy until first real update. Pre-PR41 committed only the 2-byte `t` array
while 1-byte `c`/`st` stayed lazy.

`mech.py` reconciles, per cell, the smaps residency deficit `L_b = Σ(Size − Rss)` over anon mappings
≥1 MiB at the peak-RSS snapshot against the RSS deltas: `L_zero − L_current ≈ R` and
`L_zero − L_base ≈ B`, with `B` under the per-cell 2-byte/slot ceiling. **All 8 cells CONFIRMED**;
largest residual 0.3 MiB. The mandate's open item — that zero-rep landed RSS *below* pre-PR41, i.e.
made pages lazy that were never lazy even before PR #41 — is explained, not merely plausible.

Method note that cost a pass: sampling smaps and keeping the *last* snapshot before exit catches
allocator teardown and is useless for peak accounting. `smaps2.sh` keeps the max-total-RSS snapshot.

## What this run does NOT establish

- **Nothing about speed.** Wall-clock here is contended (load1 median 36.9, max 77.4 on 16 cores) and
  is not evidence. `ooffice/max` measured a zero/current ratio of 1.077, above the preregistered 1.05
  bar, purely from contention — that cell ran at load1 55–77. The stand's quiet 1.0068 is the
  decision number. Loaded-host time ratios must never be read against preregistered speed bars.
- **Eight measured cells, seven distinct compressed outputs.** On `ooffice`, presets `max` and
  `balanced` converge to the identical archive — same canonical size 677605 and same sha256
  `4d563b48…`, as the runner's preregistered `CELLS` table already encodes for both rows. Those two
  cells are one operating point, so their agreement is an internal consistency check rather than
  independent corroboration. The stand shows the same convergence, so it is a property of the
  corpus/preset pair, not of either host. Do not read "eight cells" as eight independent compression
  outcomes.
- **No corpus aggregate.** Per-file figures only, as preregistered.
- **No claim outside these cells** — wire format, encoder defaults, `decode()`, `cube_size_limit`,
  `cm_should_try` and `prof.rs` counters are untouched and unqualified by this run.

## Round-trip accounting, stated exactly

Every decode observation used above has a byte-exact round-trip. `roundtrips.tsv` carries per-decode
rows for **120** decodes (72 timed + 24 warmup + 24 corrected-smaps), all PASS. A further 24
first-pass smaps decodes were run but never written as rows; they rest on the runner dying closed on
any sha/size mismatch (`die "archive sha256 …"`). The machine-checkable count from this directory is
therefore **120/120**, and no decode feeding any table above lacks a logged round-trip.

## Reproducing this from the repository

```
cd documentation/ephemeral/research/CUBR-ZEROREP-INDEP-20260809
python3 analyze.py   # Table in Result 2, plus per-cell medians vs the stand
python3 mech.py      # Result 3 reconciliation
sha256sum -c archives.sha256   # needs the archives; digests match the G3 SHA256SUMS
```

`analyze.py` and `mech.py` resolve their inputs under `out/`, which is a set of relative symlinks
back to the flat files in this directory. Copying this tree without preserving those symlinks breaks
both scripts with `FileNotFoundError` — that is exactly how the original delivery shipped, green
report and dead reproduction, until it was caught on re-verification.

## Corrections to the delivered report

The operator-delivered `RESULTS-CUBR-ZEROREP-INDEP-20260809.md` carried three imprecisions, all
recorded in a dated addendum there and corrected here. None touches a decision number:

1. It described the matrix as eight independent cells; it is eight measured cells over seven distinct
   compressed outputs (see above).
2. It reported `144/144` round-trips; 120 of those are logged as rows, the remaining 24 rest on
   fail-closed runner behaviour.
3. It cited a load1 median of 41.9. That figure is **not reproducible** from `loadlog.txt` — the
   median over all 268 samples is 36.9 (load5 34.8, load15 38.3). The stated maximum, 77.4, is
   correct. No result depends on this number; it is context for why wall-clock here is not evidence.

## Files

`CUBR-ZEROREP-INDEP-20260809/` — `results.tsv` (raw per-decode wall/RSS), `roundtrips.tsv` (per-decode
`cmp` status), `archives.sha256`, `loadlog.txt`, `smaps2/` (96 snapshots: peak totals, peak mappings,
series, VmHWM per cell/build), `timing_logs/` (72 `/usr/bin/time -v` logs), `runner.sh`, `runner2.sh`
(ooffice resume with a raised compress cap), `smaps2.sh`, `analyze.py`, `mech.py`, `SHA256SUMS`.
