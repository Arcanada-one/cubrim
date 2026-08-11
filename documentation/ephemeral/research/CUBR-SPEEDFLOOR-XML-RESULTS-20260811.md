# CUBR-SPEEDFLOOR-XML-20260811 — results: the CM2 speed floor is not a one-cell result

**P3 holds on a second, independent CM2 cell: 79.6× short of ninth place.** The speed floor is a
property of the rail, not an artefact of dickens. **P1 is refuted**, and its refutation is a real
methodological finding about measuring on this host — reported as stated, not explained away.

Preregistration merged to `main` as `3df3dca` at **18:48:07Z**; measurement began **18:48:32Z**.

## Predictions, scored

| | prediction | threshold | measured | verdict |
|---|---|---|---|---|
| **P1** | within 2× of the attribution-implied 0.0879 MiB/s | [0.0439, 0.1758] | **0.0302** | **REFUTED** |
| **P2** | ≥100× slower than `xz -9`, same host/pin | ≥100× | **2098×** | **HOLDS** |
| **P3** | perfect-CM2 best case < 25.69 MiB/s | ≥25.69 refutes | **0.323** | **HOLDS** |
| **P4** | best case within 2× of dickens's 0.634 | [0.317, 1.268] | **0.323** | **HOLDS** |

## P1 refuted — the profiling wall does not transfer under load

Measured 0.0302 MiB/s against the landed pinned wall's implied 0.0879 — a ratio of **0.343×**, well
outside the 2× band. The cause is host contention, and the evidence is comparative rather than
asserted:

| run | load1 range | measured / implied |
|---|---|---|
| dickens (earlier) | 9.9 – 31.2 | 0.667× |
| xml (this run) | **40.5 – 60.0** | **0.343×** |

The degradation tracks load. P1 was written assuming a pinned profiling wall transfers to benchmark
throughput within 2×; on a box shared with ~40 agent sessions at load 40–60 it does not. **The
prediction was wrong as stated and is scored REFUTED** — the useful content is that *any* absolute
MiB/s taken here carries a load-dependent penalty of 1.5–3×, so absolute throughput from this host
must never be quoted as a decision number. This is why the lane preregistered same-round ratios as
the reportable quantity.

Note the direction: contamination pushes measured throughput **down**, which pushes the perfect-CM2
best case **down** too. So it biases P3 and P4 toward *passing* on P3 and toward *failing* at the low
edge on P4. P4 passing at 0.323 against a 0.317 floor is therefore a pass **against** the bias, not
because of it — a quieter host would move it further inside the band, not out.

## Per-file measurement — xml, 5,345,280 B, median of 3 interleaved rounds

| tool | setting | ratio | decode s | MiB/s | RSS KiB | × faster than cubrim |
|---|---|---:|---:|---:|---:|---:|
| lz4 | -12 | 0.142442 | 0.020 | 254.88 | 6,144 | 8452× |
| zstd | -19 | 0.085096 | 0.030 | 169.92 | 9,088 | 5635× |
| brotli | -q11 | 0.080551 | 0.040 | 127.44 | 8,064 | 4226× |
| gzip | -9 | 0.123901 | 0.060 | 84.96 | 3,456 | 2817× |
| xz | -9 | 0.084796 | 0.070 | 72.82 | 7,552 | 2415× |
| bzip2 | -9 | 0.082537 | 0.620 | 8.22 | 4,864 | 273× |
| **cubrim** | **max** | **0.063279** | **169.040** | **0.030** | **5,844,992** | **1×** |

**No tool beats cubrim on density.** Its 0.063279 is 21.4% better than the best competitor
(brotli 0.080551), while decoding 273–8452× slower and holding **5.84 GiB** against 3.4–9.1 MiB.

Same-round ratios — the defensible quantity on a shared box:

| tool | round 1 | round 2 | round 3 | median |
|---|---:|---:|---:|---:|
| lz4 | 7344× | 3806× | 8452× | **7344×** |
| zstd | 7344× | 6343× | 4226× | **6343×** |
| brotli | 7344× | 4757× | 3381× | **4757×** |
| gzip | 2098× | 3806× | 2817× | **2817×** |
| xz | 2098× | 1730× | 2817× | **2098×** |
| bzip2 | 237× | 241× | 433× | **241×** |

## The ceiling on a second cell

`0.0302 MiB/s × 10.707 = 0.323 MiB/s` — **79.6× short of ppmd at ninth place**, against dickens's
40.5–48.7×. Driving every named CM2 component to zero cost leaves xml decoding at roughly a third of
a megabyte per second.

**P4 is the result that matters.** The perfect-CM2 best case on xml (0.323) lands inside 2× of
dickens's (0.634), from a different file, a different preset table size (`tbits=26` vs 27) and an
independently published bound (10.707× vs 13.986×). The floor reproduces. The earlier single-cell
conclusion — that no optimisation of the CM2 decode path reaches the field — now rests on two
independent cells and does not need re-scoping.

## Binary behaviour check

cubrim's xml archive is **338,244 B → ratio 0.063279**, matching the landed meta-36 figure
`0.063279` exactly. The binary built here (`8947ea9b…`) differs in bytes from the attribution's
recorded `d4b9fc85…` for the toolchain reasons established in `CUBR-BUILD-DETERMINISM-20260811.md`,
but its **output is identical**, which is what licenses applying the landed 10.707× bound to it.

Measured decode RSS 5.84 GiB matched the preregistered 5–6 GB expectation derived from `tbits=26`.

## Scope and voids

One file, `xml`, measured whole; per-file only, no corpus aggregate computed anywhere. No encoder,
wire format, preset, counter or `decode()` change; no candidate built, no lever selected — selection
is NEW-24's, which is PROGRAM's lane. No database write, no hypothesis row, no API, site or social
action.

- **Absolute MiB/s here is contaminated** (load 40.5–60.0) and P1's refutation quantifies it. Only
  same-round ratios and the pass/fail of P3/P4 should be carried forward.
- **`dickens/web` remains unmeasured.** Its component shares sum to 99.22% with no combined row
  published; deriving a bound and using it as a decision number is the step this lane refuses. It
  stays a void rather than becoming a third data point.
- The 25.69 MiB/s ninth-place marker is cross-meta, not same-host. The conclusion survives a wide
  margin of error in it — 79.6× is not a rounding question.

## Reproducing

```
cd documentation/ephemeral/research/CUBR-SPEEDFLOOR-XML-RESULTS-20260811
python3 analyze.py
```

`analyze.py` refuses to print any number if a gate is VOID or a timing row lacks a passing gate.
21 gated decode observations, 0 VOID.
