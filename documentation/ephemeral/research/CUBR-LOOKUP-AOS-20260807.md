# The lookup-layout lever, landed: one packed record, 1.41× on dickens — 87% of the whole-model ceiling

**Measured:** 2026-08-07 UTC. One candidate layout, exactly as scoped. Output
byte-identical (verified, not assumed), full suite green, byte-exact round
trip on all 12 measured decodes. Raw perf tables:
[`CUBR-LOOKUP-AOS-20260807/raw/`](CUBR-LOOKUP-AOS-20260807/raw/).

## 1. Characterisation (before the change)

Per decoded bit, CM2 consults **23 hashed `Ctr` tables** (12 order + 6
sparse + 1 indirect + 4 word; the FH4-03 column model is off on the default
path). Each table was a **struct of three parallel arrays** —
`t: Vec<u16>` (stationary prob), `c: Vec<u8>` (count), `st: Vec<u8>`
(bit-history state), each `2^tbits` entries. Every access hits the *same
hashed index* in those arrays: `predict` reads `st[i]` + `t[i]` = **2 cache
lines**; `upd` additionally touches `c[i]` = a **3rd line**. The hash mixes
`c0` per bit, so consecutive bits share no lines. Memory terms: **69
distinct random cache lines per bit** (23 tables × 3 arrays), in ~69 distinct
pages' worth of table space per touch — which is also 3× the TLB reach.
The "49 learned inputs" of the 0075 record are the mixer's view; in memory
terms the traffic is these 23 tables × 3 arrays plus the small resident
mixer/APM/match state.

## 2. The candidate and its prediction (stated before measuring)

**SoA → AoS:** pack `{t: u16, c: u8, st: u8}` into one 4-byte record,
`v: Vec<u32>`, per slot — same total memory (4 B/slot either way), same
arithmetic bit for bit, so emitted bytes cannot change. 23 lines per bit
instead of 69; predict warms the very line update writes.

Prediction, with its falsifiers: LLC-load-misses per bit fall toward
⅓–½ of stock on native-tbits decode; instructions-retired stay ~equal
(a pure stall win); whole-decode cycles improve ≥10%. Falsified if
misses/bit stay ≥ ~85% of stock or cycles move < 3%.

## 3. Gates before measurement

- **Byte-identity:** AoS-build archives of `dickens.2m`, `nci.2m`,
  `ooffice.2m` are `cmp`-identical to stock-build archives (dickens/nci
  against the archives from the 2026-08-06 sweep, ooffice against a fresh
  stock encode). A layout change that alters output bytes is not a layout
  change — verified explicitly.
- **Round trip:** every archive decoded and `cmp`-equal; every measured
  decode below round-tripped (12/12).
- **Suite:** `cargo test --release` — lib **319 passed / 0 failed / 11
  ignored** (the clean-clone baseline exactly) and every integration suite
  green, including the 7-test lossless scheme gate.

## 4. Measurement

Pinned core 0, `perf stat` hardware counts (`sudo`; `perf_event_paranoid=4`),
3 interleaved reps per cell, medians; per-bit normalisation by the fixed
16,777,216 calls. Counts, not wall-clock. Stock = `main` binary
`f3316a1e…`; AoS = this branch `ead94912…`. Archives = the native-tbits
pair from the 2026-08-06 sweep (SHA-256 in `raw/ARCHIVES.sha256`).

| file | build | cycles/bit | insn/bit | IPC | LLC-miss/bit | dTLB-miss/bit |
|---|---|---:|---:|---:|---:|---:|
| dickens | stock | 7,425.5 | 8,572.3 | 1.15 | 18.28 | 8.70 |
| dickens | **AoS** | **5,281.9** | 8,506.9 | 1.61 | **8.66** | **3.27** |
| nci | stock | 5,332.3 | 8,579.5 | 1.61 | 5.60 | 4.27 |
| nci | **AoS** | **4,560.9** | 8,548.4 | 1.87 | **2.54** | **1.17** |

**dickens: 1.406×. nci: 1.169×.** The mechanism signature is exactly the
prediction: LLC-miss ratios 0.474 / 0.453 (inside the ⅓–½ window), TLB
ratios 0.376 / 0.274 (the one-array-per-table page-reach win), and
instruction ratios 0.992 / 0.996 — the cycles came out of stalls, not out
of work.

## 5. Against the ceilings, honestly

The brief's number to hold this against was **lookup alone ≈ 1.24×**.
dickens **exceeded it (1.41×)** — not because the ceiling was wrong, but
because one packed record captures *three* budgeted effects at once: the
lookup cache share, adaptation's cache share (`upd` was the 3-line path),
and a 3× TLB-reach reduction the tbits sweep could not isolate. The right
comparator for the combined change is the whole-model perfect-layout
ceiling from the 2026-08-06 sweep — **≤1.61× dickens / ≤1.20× nci** — and
the landed result is **87% / 97% of that ceiling**, with zero density cost
(the sweep's ceiling points were bought with +23.3% output; this change
spends nothing).

What remains inside the layout budget is now small: stock-vs-AoS still
leaves 8.66 LLC misses/bit on dickens (mixer/match/StateMap traffic and the
irreducible one line per table), so further layout work is chasing ≤13% on
dickens by the same sweep bound — the update-scheme lever (≤1.99×,
algorithmic floor 38.5–40 cyc/learned-input) is the bigger remaining door.

## 6. Caveats and scope

- Cycles are core cycles under turbo; the design is comparative A/B,
  interleaved, same protocol, and the flat instruction counts rule out
  code-gen artifacts. No wall-clock claim is made anywhere.
- The shared-LLC soak inflates absolute miss counts on both sides; the
  ratios are the evidence, and the pollution can only *understate* the
  quiet-host gain.
- Encode uses the same `Ctr` code and should also benefit; not measured
  here (encode is dominated by other costs), no number claimed.
- Two files, one host, 2 MiB slices, native tbits. Corpus-wide numbers
  belong to a stand campaign, not to this host.
- No DB writes; `evaluation` stays 0; this journal is the record.

## The standing dual verdict, quoted whole

**Archival: worth pursuing** — and this lever just banked a measured 1.41×
decode on text at zero density cost. **Web: unreachable on this
algorithm** — the density WIN `0.877644` is a property of exactly the model
the web gate cannot afford; a 1.4× on a 227× gap changes nothing there, and
is not claimed to.
