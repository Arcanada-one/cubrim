# CUBR-0074 Decode Consilium

**Date:** 2026-08-03
**Status:** design-only handoff; no decoder, format, default, or database-evaluation change authorized

## Question and scope

What decode-side investigation should CUBR-0075 pursue after the CUBR-0074
reference result, and what evidence would justify selecting one optimization
direction?

The measured result is mixed but terminal for the current product gate:

- density `ratio_vs_brotli11 = 0.877644` on a 12-sample, 100% real corpus;
- candidate and Brotli-5 exact round-trips `360/360` each;
- candidate decode throughput factor `0.004410` versus Brotli-5, about 227x slower;
  reaching the fixed `0.50` gate requires roughly a 113x speedup;
- WOFF2 is the only sample above the decode gate at `0.821968`, while its density
  is `1.002286` because it is already compressed and the codec does almost no
  useful work;
- WASM is blocked on CUBR-0077 and SVG awaits an operator sourcing decision.

This is a cross-system, product-critical design fork. The existing Gate2 verdict
must remain paired: the density WIN cannot be published without the decode FAIL.

## Panel

| Panelist | Lens | Position |
|---|---|---|
| Architect (`019fc5d5-b6e0-78e2-a492-11f0648a1de1`) | decode architecture and dependency order | instrument first; table-driven entropy is the first candidate only after attribution, then SIMD; defer blocks/window changes until measured |
| Performance/SRE (`019fc5d5-b929-7c63-888c-32591ce9ffc2`) | runtime cost, browser path, and observability | conditional support for investigation; no redesign choice before stage-level profiles and browser-relevant latency/memory evidence |
| Strategist/reviewer (`019fc5d5-bb5c-75f3-9f1d-8c9f3c77261a`) | product value, reversibility, and no-go discipline | approve only a bounded investigation; do not fund or merge a multi-track optimization programme yet |

## Independent positions

### Architect

The current whole-buffer `decode(&[u8]) -> Result<Vec<u8>>` path makes the 227x
gap a broad decode-path problem, not a correctness problem. Table-driven entropy
decoding is the cleanest first experiment because it can preserve byte-identical
archives. SIMD is more credible after the decode units are regularized. Independent
blocks require stream boundaries, dictionary/reset semantics, and incremental
output, so they are a format/API decision rather than a local flag. A configurable
window is an orthogonal, lower-risk memory/cache experiment. Native ARM is
portability evidence, not a presumed speed rescue.

The registered dependencies are hypotheses, not an implementation queue:
table-driven entropy (13), native ARM (9), independent blocks (14), configurable
decoder window (17), and SIMD decode (15). Ownership between CUBR-0075 and rows
labelled CUBR-0076 must be reconciled before creating or moving work; do not
duplicate hypothesis rows.

The live ledger was read before this handoff: hypothesis IDs 9, 13, 14, 15, and
17 remain `pending_dependency` (dependency rows 3, 7, 8, 9, and 11). Dependency
5 is the only resolved row from the Gate2 reconciliation. No decode dependency
was advanced by this consilium.

### Performance/SRE

First separate codec work from startup, I/O, allocation, copying, output
materialization, and harness overhead. Capture p50/p95/p99 decode latency,
time-to-first-output, complete-output latency, decoded-MiB/s, compressed-byte/s,
cycles, branches, cache behavior, allocation counts, retained state, and page
faults. RSS alone cannot prove bounded decoder state.

The matrix must cover the 64 KiB route cliff and above it, every measured media
family, and eventually redistributable WASM/SVG representatives. The browser path
must distinguish whole-buffer from streaming, main-thread from worker execution,
first usable byte from EOF, and decode from parse/paint blocking. A CLI result is
decisive against the measured implementation but is not by itself a complete
browser-integrated product result.

### Strategist/reviewer

The density WIN is valuable research evidence but does not imply positive product
economics. The first question is whether the hot path can plausibly account for
the required 113x improvement; one optimization family would need to explain
approximately 99.1% of current decode time under an Amdahl-style upper bound.

Do not change defaults, merge a format change, create a positive evaluation, or
fund a multi-track SIMD/table/block/window effort until profiling identifies a
credible path and an opt-in real-corpus prototype demonstrates progress toward
`0.50`. A kernel microbenchmark, WOFF2, synthetic data, or density alone cannot
cross that boundary. If the product goal changes to archival/offline/bandwidth-first
use, that is a new hypothesis and needs a new gate rather than a relaxed browser
decode gate.

## Debate and resolution

| Tension | Resolution |
|---|---|
| Architect proposes table-driven entropy as the first optimization; strategist rejects choosing a direction before evidence. | Agree on a measurement-only attribution stage first. Table-driven entropy may be the first isolated experiment only if profiling identifies branch-heavy entropy work as the dominant cost. |
| Independent blocks offer architectural/browser parallelism; SRE requires single-core and browser-path viability first. | Establish single-core throughput, density cost, state bounds, and first-output semantics before measuring parallel scaling. Blocks remain a later, explicitly format/API-gated branch. |
| Missing WASM/SVG could alter workload mix; the current result is already decisive. | Keep the current numbers scoped to v2. Add licensed representatives when their gates clear; do not use missing classes either to dismiss the FAIL or to promise a rescue. |

## Converged recommendation

1. Close CUBR-0074 as a mixed result: density WIN, decode FAIL, no product-readiness
   claim, and no evaluation/evidence rows.
2. Reproduce the clean v2 candidate/Brotli-5 baseline without changing the fixed
   `0.50` gate, corpus protocol, exactness requirement, or per-sample reporting.
3. Instrument release-mode decode by stage: framing, entropy, transforms,
   match/copy, allocation, and output materialization. Measure cycles/byte,
   branches/cache, allocations, retained state, and one-core versus fixed-core
   behavior around and above 64 KiB.
4. Measure browser-relevant whole-buffer and streaming paths, including main-thread
   blocking, worker transfer, first usable output, p95/p99 latency, and memory.
5. Select at most one profile-supported, opt-in hypothesis. Start with a
   byte-preserving scalar/table or window experiment only when attribution supports
   it; then evaluate SIMD with feature dispatch and native ARM validation.
6. Defer independent blocks/container changes until single-core throughput and
   density cost are understood. Any format/API branch must define block metadata,
   reset/dictionary semantics, bounded state, and first-output behavior before
   implementation.
7. Re-run the full v2 Gate2 comparison only for a branch that demonstrates
   attributable progress and still satisfies exactness, density, tail-latency,
   and memory conditions.

## Reopen gates and no-go boundary

A future positive path requires all of the following:

- decode throughput `>=0.50` versus Brotli-5, with the threshold unchanged;
- density `<=1.00` for GO and preferably `<=0.92` for WIN;
- exact round-trips `100%`;
- no hidden per-sample, class, or p95/p99 failure;
- measured WASM/SVG coverage or an explicitly narrowed product claim;
- opt-in implementation evidence before any default or format change.

Do not merge, ship, change the default format, create a positive evaluation, or
fund a multi-track redesign until profiling supports a credible path to the
required speedup and an opt-in real-corpus prototype shows progress without
violating density, exactness, safety, or browser-path gates.

## WASM/SVG sensitivity statement

Their absence could move either headline in principle, especially if either class
has an atypical size or compressibility profile. The density result is materially
anchored by the two largest JSON/HTML resources, so ordinary missing samples are
unlikely to erase the aggregate signal. Throughput could move in either direction,
but 11/12 measured samples fail and the current factor is 0.004410; an ordinary
two-sample addition is unlikely to lift it to 0.50. This is a bounded inference,
not evidence for unmeasured classes.

## Failure-mode table

| Failure mode | Detection | Mitigation |
|---|---|---|
| Aggregate hides a class or tail failure | Per-sample, per-class, p95/p99 results | Preserve floors and publish distributions |
| “Decode” timing is actually I/O/startup/allocation | Stage profile, cycles, allocation and copy counters | Attribute before selecting an algorithm |
| SIMD helps one CPU but regresses another | x86 feature dispatch and native ARM runs | Keep scalar fallback and platform-specific gates |
| Tables increase cache pressure | Cache counters and end-to-end cycles/byte | Stop if hot-path attribution does not improve |
| Blocks improve parallelism but hurt single-core/density | Single-core and density remeasurement | Defer format change; require explicit budgets |
| Smaller window trades away density | Ratio table per sample and size band | Keep window changes opt-in and bounded |
| Missing WASM/SVG is used as a rhetorical rescue | Corpus provenance and sensitivity analysis | Scope the claim; measure when ownership clears |
| Optimization breaks exactness or malformed-input safety | Hash/byte checks and negative corpus | Keep 100% exactness and hardening gates |

**Disposition:** CUBR-0074 is closed as a defensible mixed verdict. The next
authorized question belongs to a decode-side design/measurement stage; this
consilium does not authorize starting that work in the current turn.
