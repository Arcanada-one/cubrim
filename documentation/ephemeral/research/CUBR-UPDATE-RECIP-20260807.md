# The update-scheme lever, first cut: 46 divisions become multiplies — 1.13–1.17×, byte-identical

**Measured:** 2026-08-07 UTC. One candidate, prediction stated before
measuring, all gates before measurement, counts not wall-clock. Raw perf
tables and binary/archive SHAs:
[`CUBR-UPDATE-RECIP-20260807/raw/`](CUBR-UPDATE-RECIP-20260807/raw/).

## 1. Characterisation — what one update is, and why it is serial

Per decoded bit, `update_bit(y)` performs, in dependency order after `y` is
known: 256 mixer weight updates (5×50 layer-1 + 6 layer-2; shift-based
multiply-add, no division), **23 `Ctr::upd` calls and their 23 paired
`StateMap::upd` calls — each containing one variable-divisor integer
division** (`(y·PSCALE − cur)/(cnt+2)` and `(tgt − cur)/(c+2)`), 2 APM
updates (division by constant 32 — compiled to shifts), and 3 cheap match
updates. The chain that makes it serial: the range decoder needs `p(bit)`
to produce `y`, every update needs `y`, and the *next* bit's predict reads
the updated cells. Within a bit the 46 divisions are mutually independent
(each writes its own table), so the exposure is `idiv` latency/throughput
(~26-cycle latency, ~6-cycle inverse throughput on this core), embedded in
46 load→divide→store chains. This is the "serial read-modify-write" the
2026-08-06 sweep measured as the algorithmic floor.

## 2. The candidate and its prediction (stated before measuring)

Replace both division sites with **exact reciprocal multiplication**:
`n/d = (n · ceil(2^K/d)) >> K`, exact for the full operating domain by the
Granlund–Montgomery bound — `K=24` for `Ctr` (numerator ≤ PSCALE, divisors
2–256; the bound `N·(m·d − 2^K) < 2^K` holds for every divisor since
`m·d − 2^K < d ≤ 256` and `PSCALE·256 < 2^24`), `K=33` for `StateMap`
(numerator ≤ 2^22, divisors 2–1025). Negative numerators use the unsigned
path on |n| and negate — Rust `/` truncates toward zero, so results are
identical bit for bit. The table constructor asserts the bound per divisor;
a new unit test checks `ctr_div` **exhaustively** over its whole domain
(2.1M cases) and `sm_div` at every divisor over extremes plus a dense
stride.

Prediction with falsifiers: cycles/bit improve ≥4% (hoped 8–12%);
LLC-miss/bit **unchanged ±10%** (arithmetic-only change — the strong
falsifier); instructions/bit rise ≤10% (mul-shift-select replaces one
idiv). Falsified if cycles move <2% (division not the bottleneck) or misses
shift >10% (unintended layout effect).

## 3. Gates before measurement

- **Byte-identity:** archives of `dickens.2m`, `nci.2m`, `ooffice.2m`
  `cmp`-identical to stock; round trips PASS. An update-scheme change that
  altered bytes would have been a product decision — this one provably and
  measurably does not.
- **Suite:** `cargo test --release` — lib **320 / 0 / 11** (the +1 is the
  new exactness test) and every integration suite green, including the
  7-test lossless scheme gate.
- Every measured decode below round-tripped (12/12).

## 4. Measurement

Pinned core 0, `perf stat` counts, 3 interleaved reps, medians, per-bit
over the fixed 16,777,216 calls. Baseline = `main` at `917355e` (AoS
merged; binary `eb7d4d9c…`); candidate = this branch (`fabe6511…`). Same
native-tbits archives as every prior slice (SHAs in `raw/`).

| file | build | cyc/bit | insn/bit | IPC | LLC-miss/bit | dTLB-miss/bit |
|---|---|---:|---:|---:|---:|---:|
| dickens | main-AoS | 5,547.5 | 8,507.5 | 1.53 | 9.41 | 3.31 |
| dickens | **recip** | **4,895.8** | 9,034.2 | 1.85 | 8.93 | 3.30 |
| nci | main-AoS | 4,433.8 | 8,547.7 | 1.93 | 2.95 | 1.21 |
| nci | **recip** | **3,776.8** | 9,074.6 | 2.40 | 2.70 | 1.18 |

**dickens 1.133×, nci 1.174×.** The signature is exactly the prediction:
instructions **up** 6.2% on both files, misses flat (ratios 0.949 / 0.915),
TLB flat — the cycles came out of divider latency and port pressure, not
memory. IPC 1.53 → 1.85 and 1.93 → 2.40.

(Baseline note: today's AoS-main numbers differ a few percent from
yesterday's same-build run — day-to-day thermal/turbo drift is why every
A/B here is interleaved within one session; cross-day absolute numbers are
not compared.)

## 5. Against the 1.99× ceiling, stated plainly

The ceiling (total adaptation removal) corresponds to removing 49.8% of
decode cycles. This lever removed **11.8% (dickens) / 14.8% (nci)** of
decode cycles — **~24% / ~30% of the ceiling's cycle mass**, while keeping
the model bit-exact. That is the honest fraction: a real but partial bite.
What remains inside adaptation is the irreducible-by-arithmetic part — the
read-modify-write chains themselves, the mixer's 256 weight updates, and
the StateMap/state-machine logic — reachable only by changing what the
model computes, which changes bytes and is a product decision this slice
was forbidden to take (and did not).

## 6. Cumulative — the two levers together

Against Wednesday's stock `main` (pre-AoS), measured under the same
protocol on the same archives: dickens 7,425.5 → 4,895.8 cyc/bit =
**1.517×**; nci 5,332.3 → 3,776.8 = **1.412×**. Both levers are
byte-identical, wire-untouched, decoder-compatible in both directions.
Archival-track numbers only.

## The standing dual verdict, quoted whole

**Archival: worth pursuing** — two shipped levers now measure 1.52× decode
on text at zero density cost. **Web: unreachable on this algorithm** — the
density WIN `0.877644` is a property of exactly the model the web gate
cannot afford; 1.5× against a 227× gap changes nothing there and is not
claimed to.
