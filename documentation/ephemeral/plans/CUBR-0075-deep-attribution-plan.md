---
task_id: cubr-0075-deep
title: "CUBR-0075 Deep Attribution — Per-Operation Profiling of Transforms and Entropy"
stage: measure
artifact: implementation-plan
schema_version: 1.0
created: 2025-04-06T14:20:00Z
---
# CUBR-0075 Deep Attribution Plan

## Context
The first CUBR-0075 profiling slice (792/792 exact round‑trips, 720 measured observations)
proved that **transforms (51.72 %)** and **entropy (47.70 %)** together consume **99.42 %**
of decode CPU cycles. Framing and allocation are negligible:

- **Framing (dependency 14, `independent-block-container`)** — 196,008 cycles, 0.00 %
  → **throughput relevance is dead** for any container restructuring.
- **Allocation (dependency 8, `allocator-telemetry`)** — 8,942,160,152 cycles, 0.40 %,
  90,480 calls → **throughput leverage is dead**. No allocation problem exists.

These two negative findings are measured truth and must be recorded in the 0075 evidence
as resolved dependencies.

The Amdahl arithmetic derived from the first slice shows that eliminating transforms
entirely yields at most ~2.07× speedup, and eliminating entropy ~1.91×, while the decode
gap is 227×. Therefore neither stage alone nor both together can close the gap by
optimising the current algorithm. The honest next step is **not optimisation** — it is
deeper measurement to understand *inside* transforms and entropy.

## Objective
Attribute CPU cycles inside the `transforms` and `entropy` stages to **individual
operation categories** (which transform, which entropy codec, etc.) at the same
per‑observation granularity used for the first slice. Measure exact call counts and
cycle‑counts per operation to identify the true hotspots and inform a subsequent
decision about the feasibility of a closed‑gap change.

## Constraints (what MUST NOT change)
- **Do not alter the `decode()` body, signature, or control flow.** Instrumentation is
  purely additive (opt‑in, conditional compilation), no logic modified.
- **Preserve defaults, wire format, shared backlog, and database.** Zero modification to
  hypotheses, evaluation, or the summary table.
- **Keep the existing first‑slice report intact.** The new evidence is additive and
  documented as a second profiling slice under the same 0075 task.
- **Re‑use the exact v2 corpus, warmup/trial protocol, and binary‑hash/round‑trip
  verification procedure** that produced 792/792 exact round‑trips.
- **No evaluation, no optimization, no web‑profile‑prototype activation.** This is a
  pure measurement follow‑up.

## Non‑Goals
- No changes to output, decode performance, or codegen.
- No new dependencies or backlog items.
- No start of the web decode prototype (dependency 12).
- No modification of the existing profiler binary’s default mode; the deep‑attribution
  instrument is a separate compile‑time feature flag.

## Steps

### 1. Design per‑operation categories
Identify the operation classes inside `transforms` and `entropy` with the crate‑owner.
Expected breakdown (subject to inspection):
- **Transforms** — Huffman decode, block‑replay (memcpy), symbol‑table lookup, header
  parsing, misc small operations.
- **Entropy** — Zstd decompression, raw memory copy (zero‑copy), LZMA (if any), etc.

The profiler will collect, per observation, a map `{ operation_name → (cycles, calls) }`
for every invocation that passes through the instrumentation hooks.

### 2. Add opt‑in instrumentation to `cubrim-decode-profile`
- Extend the existing conditional‑compilation attribute (e.g. `deep-profile`) so that the
  binary can be built with per‑operation tracking.
- Wrap the relevant call sites inside `transforms_*` and `entropy_*` functions with
  `#[cfg(feature="deep-profile")]` hooks that record start/end cycle counters per operation
  name. Accumulate counters in thread‑local storage and dump them after each observation
  alongside the existing stage‑level data.
- Ensure the instrumented code is bitwise identical when the feature is **not** active
  (verified by comparing SHAs of the two binaries).

### 3. Re‑run the corpus with the same protocol
- Use the exact warmup (100 iterations) and trial (720 observation) sequence from the
  first slice.
- For every one of the 720 measured observations, collect the per‑operation breakdown and
  append it to a new JSON artifact (`deep-attribution.json`).
- Verify that total cycles per observation (sum of per‑operation cycles) agrees with the
  stage‑level totals from the first slice within ±0.01 %.

### 4. Persist evidence and binary provenance
- Record **binary SHA** (for the deep‑profile build), **manifest SHA**, and **source
  commit SHA** in the artifact preamble.
- Commit `deep-attribution.json`, `deep-report.md`, and the exact profiler Cargo.lock to
  an isolated branch `codex/cubr-0075-deep` (off the existing 0075 branch).
- Do not push any changes that alter the first‑slice report or the default binary.

### 5. Write an honest report
The report (`deep-report.md`) must contain:
- The fraction of stage cycles spent in each operation, both absolute and as a percentage
  of the stage.
- Average call counts per observation for each operation, with attention to the suspicious
  ~785,000 total transform calls/observation observed in the first slice — break down
  which operation is invoked that often.
- Confirmation that framing and allocation remain negligible.
- Whether any single operation dominates within its stage, and the Amdahl ceiling each
  improvement would offer.

### 6. Verification gates
- **792/792 exact round‑trips** must be preserved; if any mismatch occurs the run is
  invalid.
- **No regression in existing test suites** (337 Rust tests, 2 focused tests, 55 Python
  tests) with the instrumentation feature left disabled.
- **Sum of per‑operation cycles** must equal the stage‑level cycle total from the first
  slice within ±0.01 % for every observation (tolerance for measurement noise).
- The profiler binary built without `deep-profile` must be **binary‑identical** to the
  first‑slice binary (SHA comparison).

### 7. Update the evidence record
- Append the two dead‑dependency cycle counts (#14: 196,008 cycles; #8: 8,942,160,152
  cycles, 90,480 calls) to the CUBR-0075 evidence document as **measured negatives**.
- Mark both dependencies as resolved (throughput‑irrelevant) in the hypotheses database
  **after** the deep attribution run confirms the numbers (can be done manually by the
  operator; the plan does not touch the DB programmatically).

## Tests
(No new tests for `decode` behaviour, because no code changes to `decode` are allowed.)
- **Sanity check**: unit test that cycles-per-operation sum equals stage total for a fixed
  corpus subset (compile with `deep-profile` and assert within 0.01 %).
- **Non‑regression**: `cargo test --all` (337 Rust), `tox` (55 Python) must pass on the
  working branch **with the deep‑profile feature off**.

## Risk
The measurement overhead of fine‑grained hooks may perturb the cycle counts slightly.
However, the guard of comparing per‑observation sums against the first‑slice stage totals
will catch any drift. If drift exceeds 0.5 %, the run is rejected and instrumentation
must be lightened (e.g. by accumulating cumulatively in trampolines with lower frequency).

## Decision post‑measurement
After the deep attribution data is collected, the Amdahl arithmetic will be re‑applied
**per operation**. Only then will the programme decide whether a bounded change (like
replacing a single transform or entropy codec) can plausibly close the path to 0.50×
decode time, or whether a clean‑room web‑decode path (dependency 12, task 0076) is
required. The data will be posted to the consilium for a gated reopen decision.