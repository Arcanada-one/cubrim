# CUBR-SAMEHOST-FIELD-20260811 — preregistration: is the ninth-place conclusion safe on a same-host basis?

**Committed to `main` BEFORE measurement.**

## The limitation this closes

Every speed-branch conclusion in this series is anchored to two numbers that were **never measured
on this host**: ppmd at **25.69 MiB/s** (ninth place) and bzip2 at **52.71** (eighth), both taken
from `world_benchmark_timing_aggregate` — a cross-meta table. `CUBR-SPEEDFLOOR-XRAY-RESULTS` named
this explicitly:

> The 25.69 / 52.71 field markers are cross-meta, not same-host. This cell is the one where that
> matters most, because 41.69 sits *between* them.

It matters more now than when that was written. The gate-passing profile put the geocm floor at
**≥28.1 MiB/s**, and the entire "at least ninth place" conclusion rests on 28.1 exceeding 25.69 — a
margin of **9%**, against a number from a different machine, a different build and a different
measurement campaign. A 9% margin cannot carry a cross-meta comparison.

7-Zip 23.01 on this host provides PPMd (`7z i` lists it), so the marker can simply be measured
instead of borrowed.

## Method (fixed before running)

Same harness and discipline as every other cell in this series:

- **Tools**: `7z -m0=PPMd` (the ninth-place reference), `bzip2 -9` (eighth), and cubrim `--preset max`
  as the anchor, all decoding **x-ray** — the file the geocm conclusion is about.
- **Interleaved**: all three decoded back-to-back within each of 3 rounds; the reportable quantity is
  the median of same-round ratios and same-window throughputs. Absolute MiB/s reported and labelled
  by host load.
- **Gates**: `cmp` **and** sha256 against the original before any timing row; a VOID aborts the cell.
- `systemd-run --scope MemoryMax=64G MemorySwapMax=0`, `taskset -c 0-15`, pin not widened.
- Compression ratio logged beside speed for every tool — these are different operating points and
  the record must not let them read as one.
- Per-file only. x-ray is one file and stays one file.

## Predictions (falsifiable)

- **P1 — cross-meta markers do not transfer.** Same-host ppmd decode throughput on x-ray differs
  from the cross-meta 25.69 MiB/s by **more than 20%** in either direction. *Refuted* if it lands
  within 20%. This tests the transferability assumption directly rather than assuming it.
- **P2 — the decision-grade one: the floor still clears ninth.** The geocm floor of **28.1 MiB/s**
  exceeds same-host ppmd throughput. *Refuted* if same-host ppmd ≥ 28.1 — in which case the
  "perfecting geocm buys at least ninth place" conclusion **does not hold on a same-host basis** and
  every record carrying it needs correcting.
- **P3 — the field ordering reproduces locally.** Same-host bzip2 decodes faster than same-host ppmd,
  preserving the cross-meta 8th-above-9th ordering. *Refuted* if ppmd is faster, which would mean the
  borrowed table's ordering does not hold here and the "eighth vs ninth" language in this series is
  unsafe regardless of magnitudes.

P2 is the one that can invalidate a published conclusion of mine. That is why it is worth running: a
9% margin resting on a foreign number is not a result, it is an assumption wearing one.

## Boundaries

No encoder, wire format, preset, counter or `decode()` change; no candidate, no lever. No database
write, no hypothesis row, no API, site or social action. Competitor tools are run as installed.
