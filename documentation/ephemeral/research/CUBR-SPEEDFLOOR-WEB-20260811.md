# CUBR-SPEEDFLOOR-WEB-20260811 — preregistration: closing the dickens/web void, and testing whether the floor's margin is uniform

**Committed to `main` BEFORE measurement.**

## The void this closes, and why it can now be closed honestly

Two prior lanes held `dickens/web` back as an explicit void with the same reason:

> its component shares sum to 99.22% with **no combined row published**, and deriving a bound then
> using it as a decision number is the step this lane refuses.

That refusal was right at the time, because a bound guessed from a rounded table is not evidence. It
is no longer necessary: the G2 attribution committed its **raw** per-symbol data
(`CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/analysis/symbols.tsv`, 752 rows, with a `bucket` column),
which is the source the published bounds were computed from.

So the bound is **derived and then validated against the two published answers before being used**:

| cell | Σ `cm2_*` | `cm2_decode_shell` | per-bit machinery | bound | published | match |
|---|---:|---:|---:|---:|---|---|
| dickens/max | 93.310% | 0.46% | **92.85%** | **13.986×** | 92.85% / 13.986× | **EXACT** |
| xml/max | 91.240% | 0.58% | **90.66%** | **10.707×** | 90.66% / 10.707× | **EXACT** |
| dickens/web | 99.220% | 0.66% | **98.56%** | **69.444×** | *(unpublished)* | derived |

The rule — sum the `cm2_*` buckets, exclude `cm2_decode_shell` because the outer shell is not per-bit
machinery — reproduces **both** published bounds to three decimals. A naive sum of all `cm2_*`
buckets does not (it gives 14.948× and 11.416×), which is exactly why the earlier refusal was
correct. Validated on two known answers, the same rule applied to `dickens/web` is evidence, not a
guess.

## Why this cell is the strongest available test

`dickens/web` has a bound of **69.444×** — five times dickens/max's 13.986×, because the `web` preset
uses far smaller tables, so per-bit CM2 machinery dominates an even larger fraction of decode time.
Applying it to the landed pinned wall of 105.710 s (9.7203 MiB → **0.0920 MiB/s** implied) gives a
perfect-CM2 best case of **6.386 MiB/s** — only **4.0× short** of ninth place, against dickens/max's
40.5× and xml/max's 79.6×.

This is therefore the cell most likely to refute P3, and the first that could show the speed floor's
*margin* is not uniform.

## Predictions (falsifiable)

- **P1 — calibrated transfer, not naive transfer.** Prior runs measured/implied at **0.667×**
  (load1 9.9–31.2) and **0.343×** (load1 40.5–60.0). Predict this run's measured/implied falls in
  **[0.30, 1.00]**. *Refuted* outside. This replaces the naive "within 2× of implied" prediction that
  was refuted on xml; it is a real prediction because it can still fail in both directions.
- **P2 — the same-host gap stays ≥100×.** cubrim on `dickens/web` is ≥100× slower than `xz -9`
  decoding dickens on this host and pin. *Refuted* below 100×.
- **P3 — the field is still unreachable.** measured throughput × 69.444 < **25.69 MiB/s**.
  *Refuted* at or above. This is the decision-grade prediction and the one this cell genuinely
  threatens.
- **P4 — the floor's MAGNITUDE is not uniform across presets.** Predict this cell's perfect-CM2 best
  case lands **outside** 2× of dickens/max's 0.634 MiB/s, i.e. outside [0.317, 1.268].
  *Refuted* if it lands inside.

P4 is deliberately stated in the **opposite** direction from the xml lane's P4, which predicted the
best cases would agree within 2×. On xml they did. Here the mechanism says they should not: a preset
that shrinks the tables raises the CM2 share and therefore the ceiling. If P4 holds, the correct
reading of the whole speed-floor result is refined — *"the field is unreachable on the CM2 rail"*
survives, but *"the floor is one number"* does not, and web-class operating points sit far closer to
the field than max-class ones.

## Method (fixed before running)

- **Binary**: the attribution's own frozen commit `3a13f486` (sha256 `8947ea9b…`), so the derived
  bound applies to this binary. Behaviour equivalence checked by archive bytes, as in the prior two
  cells.
- **Preset `web`**, matching the landed cell. Prior zero-rep data puts web-preset decode RSS near
  110 MB, two orders below `max` — a `MemoryMax=64G` scope is retained anyway, and the observed RSS
  is reported against that expectation.
- **Competitors on the same host and pin**: xz -9, zstd -19, brotli -q11, gzip -9, bzip2 -9, lz4 -12,
  decoding the same `dickens` file.
- **Interleaved**: all seven tools decoded back-to-back within each of 3 rounds; the reportable
  quantity is the **median of same-round ratios**. Absolute MiB/s is reported and labelled
  contaminated.
- **Gates**: `cmp` **and** sha256 against the original before any timing row is written; a VOID gate
  aborts the cell.
- `taskset -c 0-15`, pin not widened. Ratio logged beside speed. Per-file only, no corpus aggregate.

## Boundaries

No encoder, wire format, preset definition, counter or `decode()` change. No candidate built, no
lever selected — selection is NEW-24's, PROGRAM's lane. No database write, no hypothesis row, no API,
site or social action.
