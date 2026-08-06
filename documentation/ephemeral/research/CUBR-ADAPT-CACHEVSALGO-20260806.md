# Adaptation is an algorithmic cost, not a cache problem — measured, with both ceilings stated

**Measured:** 2026-08-06 UTC, core-0-pinned rdtsc attribution + hardware
counters, byte-exact round trip on all 12 sweep points. Provenance and raw
evidence: [`CUBR-ADAPT-CACHEVSALGO-20260806/`](CUBR-ADAPT-CACHEVSALGO-20260806/provenance.txt).
**The one-sentence question, answered:** adaptation's 56.1 cycles per learned
input is **mostly algorithmic** — with the model tables shrunk until LLC
misses fall 94–96% and TLB misses go to ~zero, adaptation keeps **64%**
(dickens) to **85%** (nci) of its per-call cost. The cache-sensitive part of
the model is `counter_state_lookup`, not adaptation.

## Method — one knob, one discriminating axis

`CUBRIM_CM2_TBITS` (the committed sweep cap; same both-sides protocol as the
CUBR-0087 memory sweep) at {native=24, 22, 20, 18, 15, 12} on `dickens.2m`
and `nci.2m`. Table working set spans **1,508 MiB → 7 MiB**; the per-bit call
count (16,777,216) and the update arithmetic are identical at every point, so
model-split cycles/call compare exactly. Instrument: the CUBR-0075 decode
profiler at its recorded base commit (rdtsc, TSC 3.600 GHz confirmed
in-file), plus `perf stat` cache/TLB counts on a second pinned run.

## Results (cycles per call; misses per call)

| file | tbits | RSS MiB | `adaptation` | `lookup` | `dot` | LLC-miss/c | TLB-miss/c | IPC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dickens | native | 1,507.7 | 2,948.5 | 1,822.4 | 959.5 | 16.95 | 8.60 | 1.19 |
| dickens | 22 | 412.7 | 2,799.2 | 1,686.8 | 945.2 | 14.98 | 8.43 | 1.20 |
| dickens | 20 | 112.0 | 2,527.3 | 1,558.9 | 859.5 | 13.26 | 7.99 | 1.27 |
| dickens | 18 | 34.1 | 2,592.3 | 1,482.9 | 960.1 | 10.06 | 6.65 | 1.33 |
| dickens | 15 | 10.8 | **1,885.9** | **665.9** | 899.9 | **1.02** | **0.14** | 1.63 |
| nci | native | 1,396.6 | 2,273.6 | 1,018.7 | 909.4 | 5.28 | 4.22 | 1.48 |
| nci | 22 | 383.4 | 2,045.1 | 908.2 | 835.7 | 4.42 | 4.11 | 1.52 |
| nci | 20 | 109.2 | 2,151.9 | 932.0 | 895.7 | 4.10 | 3.85 | 1.51 |
| nci | 18 | 33.5 | 2,239.8 | 904.5 | 976.6 | 2.97 | 2.95 | 1.64 |
| nci | 15 | 10.1 | 1,942.3 | 622.5 | 914.2 | 1.40 | 0.16 | 1.62 |
| nci | 12 | 7.1 | **1,961.3** | **576.6** | 951.6 | **0.19** | **0.01** | 1.66 |

Built-in sanity check: `dot_products` — pure arithmetic with no table
dependence — is flat across the entire sweep (900–977 everywhere, ±6%). The
instrument responds to working set only where a working set exists.

## The discrimination

Going from native tables to cache-resident tables removes **94% (dickens) /
96% (nci) of LLC misses** and essentially all TLB misses. If adaptation were
cache-bound, its cycles would collapse with them. Measured:

- `model.adaptation`: **−36.0%** (dickens 2,948.5 → 1,885.9) and **−14.6%**
  (nci 2,273.6 → 1,942.3). The floor — **38.5–40.0 cycles per learned
  input** with a near-zero miss rate — is the serial read-modify-write
  arithmetic itself.
- `model.counter_state_lookup`: **−63.5%** (dickens) / **−43.4%** (nci) —
  *this* is where the memory hierarchy lives, as expected for hashed table
  probes.

**Verdict: algorithmic.** Cache effects explain at most a third of
adaptation on text and a seventh on nci; the rest survives full cache
residency. The two candidate fixes the brief distinguished now have measured,
different ceilings.

## The ceilings, stated before any fix (as required)

- **Data layout (perfect):** if a layout change made the *entire model* behave
  as its cache-resident self at native density, the whole-decode ceiling is
  **≤1.61×** on dickens (model cycles/call 5,730.4 → 3,451.7, −39.8%, model =
  95.55% of decode) and **≤1.20×** on nci. Note the sweep *bought* residency
  with density (+23.3% dickens at tbits 15; +4.4% nci) — a real layout fix
  gets no such discount and can only approach these bounds from below. And
  most of the layout headroom belongs to **lookup**: fixing lookup alone is
  **≤1.24×** (dickens), while fixing adaptation's cache share alone is
  **≤1.21×**.
- **Update-scheme replacement (algorithmic lever):** adaptation is 49.8% of
  decode cycles (52.09% of a 95.55% model share), so *complete* removal —
  the unreachable limit — is **≤1.99×**; any realizable replacement scheme is
  bounded below that, against a measured floor of ~38.5–40 cyc/learned-input
  (× 49 learned inputs per bit) that is pure serial arithmetic.

Both ceilings are archival-scale levers (there is no 227× wall on this
track): a genuine ~1.5–2× decode improvement on CM2-won text is available in
principle, split roughly evenly between a memory-layout attack on `lookup`
and an algorithmic attack on the update scheme — and nothing bigger is,
short of a different model.

## Bonus finding — the rail self-protects below tbits 15

At `tbits=12` on dickens the emitted outer mode flips from CM2 to MODE_LZ:
the capped CM2 candidate loses the competitive rail entirely. Any future
memory preset below tbits 15 must expect CM2 to stop being the winner on
text — the competitive-min architecture degrades gracefully rather than
shipping a bad CM2. (nci keeps CM2 through tbits 12 at +14.7% output.)

## Discipline

No fix is implemented in this slice. No DB row is written; `evaluation`
stays 0; this journal is the designed home for pre-evaluation measurement.
No wall-clock number is claimed anywhere — cycles under fixed pinning and
hardware-counter counts only, with the LLC-pollution caveat recorded in
provenance (it biases toward the hypothesis that *lost*). Round trips:
12/12 sweep points byte-exact via the stock binary plus the profiler's own
per-run exact-roundtrip assertion on all 11 profiled points.

## The standing dual verdict, quoted whole

**Archival: worth pursuing** — best single split 2.09×, whole model 22.52×,
and the open adaptation question is now answered with measured ceilings.
**Web: unreachable on this algorithm** — density WIN `0.877644` never ships
without decode `0.004410` in the same sentence; the density WIN is a property
of exactly the model the web gate cannot afford.
