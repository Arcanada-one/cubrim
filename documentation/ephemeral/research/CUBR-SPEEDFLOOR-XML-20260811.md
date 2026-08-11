# CUBR-SPEEDFLOOR-XML-20260811 — preregistration: is the CM2 speed floor a one-cell result?

**Committed to `main` BEFORE measurement.** Ceiling derived from landed evidence and arithmetic.

## Why this cell

`CUBR-SPEEDFLOOR-RESULTS-20260811.md` concluded that the CM2 decode path cannot reach the competitive
field: on `dickens/max`, driving every named CM2 component to zero cost gives 0.53–0.63 MiB/s, 41–49×
short of ninth place. **That conclusion rests on exactly one clean CM2 cell.** Its own scope section
names the gap:

> `xml/max` and `dickens/web` were not measured, though both have landed ceilings. Only `xml/max`
> has a stated combined bound (10.707×).

A structural claim about a rail should not stand on a single file. This lane measures the second — and
only remaining — CM2 cell with a *published* combined bound, so the floor is either corroborated on an
independent file or shown to be a dickens artefact.

`dickens/web` stays excluded: its component shares sum to 99.22% with **no combined row published**,
which would imply a very large bound. Deriving one myself and then using it as a decision number is
exactly the unverified step this lane refuses.

**Coordination.** PROGRAM holds NEW-24 (tier ladder) and currently has PR #110 open on H-33. This lane
touches neither: no candidate is built, no lever selected, no encoder change.

## Ceiling, before measurement

xml is 5,345,280 B = 5.0977 MiB. `tbits = clamp(ceil(log2 len)+3, 18, 27) = 26`, so its CM2 tables are
half dickens's — memory is expected near 5–6 GB, not 10.5.

Landed G2 attribution for `xml/max`: plain pinned profiling wall **58.000 s**, named CM2 machinery
**90.66%**, combined outer bound **10.707×** (`predict_bit` 50.01%, `Ctr::upd` 29.42%,
`update_bit` 8.50%).

| quantity | value |
|---|---|
| attribution-implied rate | 5.0977 / 58.000 = **0.0879 MiB/s** |
| × 10.707 combined bound | **0.941 MiB/s** |
| ninth place (ppmd, cross-meta marker) | 25.69 MiB/s |

So the preregistered expectation is that perfecting every named CM2 component on xml still lands
**below 1 MiB/s**, ~27× short of ninth place — the same shape as dickens.

## Predictions (falsifiable)

- **P1 — the profiling rate transfers.** Measured cubrim decode throughput on `xml/max`, gated and
  pinned, lands within 2× of 0.0879 MiB/s, i.e. **[0.0439, 0.1758]**. *Refuted* outside.
- **P2 — the same-host gap is ≥100×.** cubrim is ≥100× slower than `xz -9` decoding xml on this host
  and pin. *Refuted* below 100×.
- **P3 — the field stays unreachable.** measured throughput × 10.707 < **25.69 MiB/s**. *Refuted* at
  or above.
- **P4 — the floor is a rail property, not a dickens artefact.** xml's perfect-CM2 best case lands
  within 2× of dickens's 0.634 MiB/s, i.e. **[0.317, 1.268] MiB/s**. *Refuted* outside that band —
  which would mean the floor varies enough per file that a single-cell conclusion was unsafe, and the
  dickens result should be re-scoped.

P4 is the reason this cell is worth measuring. P1–P3 repeating on a second file is corroboration; P4
is the one that can actually overturn how the earlier result should be read.

## Method (fixed before running)

- **Binary**: the attribution's own frozen commit `3a13f486`, so the landed 10.707× applies to this
  binary rather than being mixed across commits. Binary sha256 recorded; note this differs from the
  attribution's recorded sha for toolchain reasons already established in
  `CUBR-BUILD-DETERMINISM-20260811.md` — behaviour equivalence, not binary identity, is what licenses
  the comparison, and it is checked by archive bytes.
- **Competitors on the same host and pin**: xz -9, zstd -19, brotli -q11, gzip -9, bzip2 -9, lz4 -12.
  Not read from a cross-meta table.
- **Interleaved by default.** The dickens run showed absolute wall-clock on this shared box is
  unusable across windows (bzip2's ratio alone swung 110×→418×). Every tool is decoded back-to-back
  within each of 3 rounds; the reportable quantity is the **median of same-round ratios**. Absolute
  MiB/s is reported but labelled contaminated if load is high.
- **Gates before measurement**: every decode verified by `cmp` **and** sha256 against the original
  before its timing row is written; a VOID gate aborts the cell.
- **Resource discipline**: `systemd-run --user --scope -p MemoryMax=64G -p MemorySwapMax=0`,
  `taskset -c 0-15`. Pin not widened. (8G was proven too small on full files — tbits saturation.)
- **Ratio logged beside speed**, so the density/speed trade cannot be collapsed into one number.
- Per-file only. No corpus aggregate, no corpus-wide average — xml is one file and stays one file.

## Boundaries

No encoder, wire format, preset, counter or `decode()` change. No candidate built, no lever selected.
No database write, no hypothesis row, no API, site or social action.
