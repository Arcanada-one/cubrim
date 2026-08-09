# Results: decode-time attribution at the world-benchmark operating point

**State:** MEASURED. Preregistration: `CUBR-DECODE-ATTRIB-20260809.md` (landed
on `main` @ d212c1c via PR #51 BEFORE this run). Run executed 2026-08-09
12:33–13:14 UTC on dev-ai, binary `/root/phaseC/cubrim-3a13f48` (sha256
`d4b9fc85a242f887…0211cb` — the exact Phase C campaign binary), pinned
`taskset -c 16-19`, `CUBR_THREADS=4`, campaign thread semantics. Raw
artifacts: `dev-ai:/root/cubr-decode-attrib-20260809/` (journal.jsonl,
per-cell perf.data, pstat*.txt, perf-report.txt, plain.time).

## Gates

Every reported cell passed all preregistered gates:

- **G1 (canonical archive identity):** the freshly produced archive matched
  the Phase C journal sha256 on all four cells — dickens/max `b39d5043…`,
  xml/max `d64f83f3…`, x-ray/max `4ed8a550…`, dickens/web `a77d540d…`. The
  operating point reproduces byte-exactly from source corpus + campaign
  binary.
- **G2 (round-trip):** every profiled decode output passed `cmp` and sha256
  against the corpus original. 16/16 decodes clean.
- **G3 (instrument overhead ≤10%):** dickens/max 1.025, xml/max 1.038,
  dickens/web 1.018 — pass. **x-ray/max 1.223 — FAIL**: its perf-record
  symbol shares are reported below flagged *instrument-perturbed* per the
  preregistration; its perf-stat rows (separate unperturbed decodes) are
  clean.
- Same-cell perf-stat agreement: total cycles within 0.3% on every cell.

**Void record:** the first xml/max attempt voided on "source file missing" —
the runner's `CORPUS=/root/corpus` root lacks xml; the campaign root is
`/root/corpus-full`. The cell was re-run with the corrected root under
identical gates (journal records both). dickens and x-ray in the flat root
were sha256-verified canonical, so no other cell was affected.

## Per-cell numbers (per-file figures only; wall-clock from the plain,
uninstrumented decode; counters from pstat1 — pstat2 within 0.3%)

| cell | decode wall s | campaign wall s (meta 36/38) | cycles/bit | insn/bit | IPC | LLC-miss/bit | dTLB-miss/bit | page-faults | decode peak RSS |
|---|---|---|---|---|---|---|---|---|---|
| dickens/max | 143.80 | 144.01 | 5,962 | 8,682 | 1.46 | 48.8 | 10.0 | 3,950,937 | 10.54 GiB |
| xml/max | 58.27 | 58.00 | 4,608 | 8,695 | 1.89 | 40.2 | 9.0 | — | 5.57 GiB |
| dickens/web | 104.63 | — (preset web meta 38) | 4,308 | 8,061 | 1.87 | 36.5 | 8.1 | 43,405 | 116.5 MiB |
| x-ray/max | 6.08 | 6.23 | 2,407 cyc/**byte** | 5,802 insn/**byte** | 2.41 | 24.1/byte | 1.66/byte | 21,832 | 88 MiB |

Reproduction fidelity: plain walls land within 0.5% of the campaign's
recorded decompress_ms on all three max cells — the operating point is
reproducible, not merely archived.

**Decode is single-threaded in practice:** task-clock/elapsed = 1.000 CPUs on
every cell despite `CUBR_THREADS=4`. The CM2 stream is one whole-file
range-coded stream; there is nothing to parallelise without a wire change
(that would be a product decision, recorded here as an observation only).

## Symbol attribution (perf record, cycles)

dickens/max — and xml/max within 3 points of every row (bracketed):

| symbol | share |
|---|---|
| `CmModel::predict_bit` (23 table probes + 3 match + stretch + both mixer layers + APM refine, all inlined) | **49.91%** [49.79%] |
| `Ctr::upd` (random RMW write-back of probed slots + StateMap update) | **32.76%** [30.05%] |
| `CmModel::update_bit` (mixer/APM update arithmetic; calls out to Ctr::upd counted above) | 6.40% [8.25%] |
| `Match::end` / `start_byte` (per-byte hashing) | 3.63% [2.38%] |
| `cm2_decode` (range decoder + outer loop) | 0.45% [0.59%] |
| kernel page-fault path (`clear_page_rep` + `asm_exc_page_fault`) | 0.93% [1.24%] |

dickens/web: same shape — 54.45 / 32.35 / 8.37 / 3.30 / 0.66.

x-ray/max (*instrument-perturbed, G3 1.223 — shares only, no cycle figures*):
`geocm::decode_stream_mix` 84.84%, `geocm::Mixer::update` 12.67%,
`geocm::mix_ctxs` 0.69% — **CM2 ≈ 0%**. The image-class decode path is the
geocm nested coder inside the MED16 container, consistent with F17.

`perf annotate` inside `predict_bit` (dickens/max, the preregistered fallback
for inlining): the hottest single site is a *dependent load pair* — extract
the state byte, then an indexed u32 table load — carrying ~29.6% of the
symbol's samples, with the remaining probe loads spread at 1–3% each. Cycles
concentrate on load-dependency stalls, not on the mixer's multiply-accumulate
runs.

## Preregistered predictions — verdicts

- **P1 CONFIRMED.** CM2 per-bit machinery: 93.2% (dickens/max), 91.1%
  (xml/max) ≥ 85%. Range coder 0.45–0.59% ≤ 5% — the encode-side F12 figure
  (2.0%) holds at decode too; an infinitely fast entropy coder buys ≤1.006×.
- **P2 REFUTED.** The mixer is not the largest bucket at any measurable
  granularity. The separable buckets are probe-read latency inside
  `predict_bit` (~50%) and `Ctr::upd` write-back (~33%); annotate shows the
  op-count argument failed because cycles follow load-dependency chains, not
  instruction counts.
- **P3 CONFIRMED by its committed criterion, with an honest caveat.** IPC ≥
  1.0 on every CM2 cell (1.46 / 1.87 / 1.89) — the loop is not
  memory-latency-*dominated*. But the caveat is load-bearing: from `max` to
  `web` on the same bytes, instructions fall only 7% while cycles fall 28%
  and IPC rises 1.46→1.87 — the entire preset speedup is reduced memory
  stalling. Even `web`'s ~108 MiB tables exceed this CPU's 16 MiB CCX-local
  L3, so misses/bit stay high (36.5) at every preset. The regime is mixed:
  latency chains over dependent random loads, throughput-limited nowhere.
- **P4 CONFIRMED.** x-ray decode has ≈0% CM2; geocm is 98.2%.
- **P5 CONFIRMED.** web attribution shape equals max within ±5 points on
  every bucket.

## Honest Amdahl ceilings (dickens/max shares; the map this run exists to produce)

| lever direction | attacks | ceiling |
|---|---|---|
| Eliminate `Ctr::upd` write-back entirely (impossible; bound only) | 32.8% | 1.49× |
| Halve `predict_bit` (e.g. halve the model count → fewer dependent loads AND fewer write-backs AND narrower mixer — shares compound) | ~50% + proportional `Ctr::upd` share | ~1.7–2.5× (compound, needs its own prediction) |
| Perfect entropy coder (NEW-22-class rANS on the CM path) | 0.45% | **1.005× — dead**, decode-side confirmation of F12 |
| `--preset web` (already shipped) | table size → stalls | **1.37× measured** at +5.65% ratio (F10) — a product trade, on the record |
| Kernel/fault path at max | 0.93% | 1.009× (zero-rep PR #47 targets RSS, not speed — consistent) |
| Replace the whole CM2 loop on CM2-won files (NEW-24 Fast-CM product frame) | ~93% | bounded by the non-CM2 residue: ~14× on dickens — the flagship's honest outer bound |
| geocm decode (image class only) | 98.2% of x-ray decode | the x-ray/mr/sao lever lives here, not in CM2 — and it is the same coder the narrowed NEW-08 targets for ratio |

## What this licenses

The characterisation the mandate asked for is: **the 0.087 MiB/s is ~50%
dependent random-load latency in 23-way model probing, ~33% random RMW
write-back of the same tables, ~7% mixer/APM update arithmetic, ≤0.6% entropy
coding, ~1% kernel faults — on a single thread, in a mixed
latency-chain/compute regime that no single-component lever can move more
than ~1.5× except model-count reduction, which compounds across probe,
write-back and mixer simultaneously.** Any Fast-CM (NEW-24) design should be
priced against this map: the lever with the largest compound ceiling is
fewer-models-per-bit (time-budgeted model selection), not SIMD arithmetic and
not a faster coder. No lever is proposed here; the next step per protocol is
a preregistered prediction for a specific candidate.

No DB rows were written. Absolute throughput from these pinned profiling runs
is not quotable as campaign timing and has not been quoted as such.
