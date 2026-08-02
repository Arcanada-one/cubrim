# CUBR-0074 Gate 2 Reference Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` (recommended, when your runtime supports spawning isolated agents) or `executing-plans` (single-session execution) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the existing `cubrim-lowmem-decode` CLI as an explicitly non-Web-Profile reference without changing the published five-codec Phase A comparison.

**Architecture:** Add a separate reference-channel adapter list and bundle protocol. Keep `PHASE_A_CODECS`, the published bundle verifier, and the existing five-codec run path unchanged. Reuse the runner's immutable manifest, sandbox, provenance, exact round-trip, and five-metric machinery for the candidate channel.

**Tech Stack:** Python 3 benchmark harness, Rust `cubrim` CLI, PostgreSQL `web_benchmark_*` schema.

---

### Task 1: Preserve the preregistered gate

**Files:**
- Create: `documentation/ephemeral/research/CUBR-0074-gate2.md`
- Modify: PostgreSQL `web_benchmark_hypothesis_criterion` row 57 in place

- [x] Record ratio against Brotli-11, decode throughput against Brotli-5, the fixed 0.50 factor, exact round-trip, and the separate reference-channel disclosure.
- [x] Amend criterion 57 from `decode_throughput_vs_brotli11 >= 0.25` to `decode_throughput_vs_brotli5 >= 0.50` only after a fresh DB backup and before candidate measurement.

### Task 2: Add the reference adapter without changing Phase A

**Files:**
- Modify: `bench/web-benchmark/adapters.py`
- Modify: `bench/web-benchmark/capabilities.py`
- Modify: `bench/web-benchmark/run.py`
- Test: `bench/web-benchmark/tests/test_attribution_gate.py`
- Test: `bench/web-benchmark/tests/test_runner.py`
- Test: `bench/web-benchmark/tests/test_summarize.py`

- [x] Add an explicit `cubrim-lowmem-decode` adapter with target-aware argv `compress INPUT OUTPUT --preset lowmem-decode -q` and `decompress INPUT OUTPUT -q`, immutable binary provenance, and `web_profile: false`.
- [x] Expose the adapter only through a `reference_phase_a` entry point; leave the exact five-codec `PHASE_A_CODECS` tuple and its default bundle verification contract unchanged.
- [x] Add tests proving the published five-codec list is unchanged, the candidate is rejected from `cubrim-web`, and the reference bundle requires the same 30 trials, 3 warmups, five metrics, and exact round-trip fields.

### Task 3: Verify, measure, and write only validated web-schema evidence

**Files:**
- Modify: PostgreSQL `web_benchmark_hypothesis_dependency`, only after all cells validate
- Insert: PostgreSQL `web_benchmark_hypothesis_evaluation`, `web_benchmark_hypothesis_evidence`, and `web_benchmark_hypothesis_derived`

- [ ] Run the focused Python harness tests and prove the published five-codec Phase A bundle remains byte-identical.
- [ ] Run the reference channel on the same eight samples with 30 trials and 3 warmups; require exact decoded hash and length on every cell.
- [ ] Summarize medians and bootstrap intervals, compare ratio to Brotli-11 and decode throughput to Brotli-5, then write guarded DB evidence only for complete validated cells.
- [ ] Leave the dependency pending and write a journaled void instead of numeric rows if any candidate cell fails.
- [ ] Do not touch CUBR-0076 through CUBR-0080 or advance WC-STAGE-1.
