---
task_id: CUBR-0075
artifact: plan
schema_version: 1
captured_at: 2026-08-03
captured_by: codex
complexity: L3
prd_status: waived
code_sha_at_plan: 7073583
source_mandate: /home/dev/LUNA-0075PROFILE.md
---

# CUBR-0075 — Decode Attribution Profile, First Slice

This plan executes only the first slice in `/home/dev/LUNA-0075PROFILE.md`: release-mode
decode attribution for the v2 corpus. It is not an optimization plan and does not open a
new task. The existing public decoder and archive wire format remain the contract.

## Outcome

Deliver a separately built, explicitly opt-in `cubrim-decode-profile` binary and a
reproducible runner that produce persistent JSON evidence for:

- framing, entropy, transforms, match/copy, allocation, and output materialization;
- elapsed time and cycles per decoded byte where the host can provide cycles;
- allocation count, allocated bytes, peak live bytes, and retained bytes after decoder
  state is dropped;
- the 12 samples in `bench/web-corpus/manifest.v2.json`, including the five samples
  above 64 KiB and the seven below it;
- a single-threaded unpinned run (`one-core`) versus the same process pinned to CPU 0
  (`fixed-core`), with the affinity command recorded; and
- a byte-exact SHA-256 round-trip for every sample.

The final research report will state where the measured decode cost resides only after
the evidence file is complete. It will not convert attribution into an evaluation or
optimization verdict.

## Boundaries and non-goals

- Do not edit the signature or body of `pub fn decode()` in `code/cubrim-rs/src/codec.rs`.
  Additive opt-in entry points and internal instrumentation are allowed by the mandate.
- Keep the default build and all default CLI behavior unchanged. The profiler is behind
  a `decode-profile` Cargo feature and a separate binary target; the feature is off by
  default and the target requires it.
- Do not change the archive format, `encode`, the published benchmark harness, the
  database, the shared backlog, or foreign worktree files.
- Do not add database evaluation/evidence/derived rows in this slice. A void or blocker
  belongs in a journal/report, not a fabricated numeric row.
- Do not implement block decoding, streaming decode, bounded-window experiments, ARM,
  SIMD, or any other pending hypothesis. Do not optimize a hot path while measuring it.
- Do not claim that RSS, allocator counters, or a green test suite proves bounded-state
  behavior. Report the exact metric and its scope.

## Design

### Opt-in instrumentation

Add `decode-profile = []` to `code/cubrim-rs/Cargo.toml`, plus a
`cubrim-decode-profile` binary with `required-features = ["decode-profile"]`. Add
`code/cubrim-rs/src/decode_profile.rs`, compiled only for that feature, with:

- a thread-local per-decode accumulator so profiling is deterministic and does not add a
  global lock to the normal decoder;
- named stage totals for the six mandated stages, including call counts and decoded-byte
  denominators;
- `Instant` elapsed time and an x86_64 serialized cycle counter when available, with an
  explicit `cycles_supported`/source field instead of a guessed value on other hosts;
- an additive begin/finish/report API used only by the profiler binary; and
- serde output whose schema is tested before corpus measurement.

Instrument only the internal decode paths exercised by the v2 archives. For the current
CM2 path, the hooks belong around header validation (framing), decoder/model allocation,
range/model work (entropy), model context updates (transforms), and output pushes
(materialization). CM2 performs no match/copy operation; its report must say
`applicable: false` for that stage rather than treating zero as a measured win. If a v2
archive selects an uninstrumented mode, the runner fails closed and records the mode as a
blocker before any aggregate claim.

The profiler binary owns a counting global allocator. It resets counters immediately
before the decode, snapshots peak/live allocation around decode, and takes a second live
snapshot after the returned output is dropped. The report distinguishes decoder-retained
bytes from the output buffer and from process setup allocations.

### Persistent runner and provenance

Add `bench/web-benchmark/profile_decode.py`. It will:

1. validate the v2 manifest and its payload SHA-256 values;
2. build or receive the release `cubrim` reference binary and create one archive per
   payload using the already validated `compress --preset lowmem-decode --b 1024 -q`
   route, without changing the candidate implementation;
3. run the profile binary for three warmups and 30 measured trials per sample in both
   affinity modes;
4. pass each original payload to the profiler for exact round-trip verification;
5. preserve every raw observation, median, denominator, host/CPU/affinity description,
   reference-binary SHA, profiler SHA, source SHA, and manifest SHA; and
6. write the aggregate evidence to
   `documentation/ephemeral/research/CUBR-0075-profile/attribution.json`.

The script must use `taskset` only when available and must fail closed if the requested
fixed-core command cannot be verified. “One-core” means one decoder thread without an
affinity mask; “fixed-core” means that same single decoder thread under `taskset -c 0`.
The report will explicitly describe this comparison as scheduler/affinity context, not
as a parallelism benchmark. A compact, human-readable conclusion goes in
`documentation/ephemeral/research/CUBR-0075-profile/attribution.md`.

## TDD and implementation sequence

### 1. RED: telemetry contract and runner contract

Create focused tests before production instrumentation:

- `code/cubrim-rs/src/decode_profile.rs` tests for the six-stage schema, per-byte
  denominators, unavailable-cycle encoding, call-count accumulation, and the fact that a
  fresh profile is empty until explicitly started;
- `code/cubrim-rs/tests/decode_profile.rs` tests for the additive profile entry point on a
  small CM2 round-trip, including exact output and nonzero framing/allocation/output
  fields; and
- `bench/web-benchmark/tests/test_profile_decode.py` tests for manifest SHA validation,
  64 KiB band classification, exact-hash rejection, affinity argv construction, and
  fail-closed handling of an unsupported decoder mode using deterministic fakes.

Run the focused tests and confirm they fail for the missing API/schema before adding the
implementation.

### 2. GREEN: feature-gated profile API and allocator

Implement `src/decode_profile.rs` and
`src/bin/cubrim_decode_profile.rs` with no new third-party dependencies. Keep all
feature-off code paths absent at compile time. The binary accepts explicit input,
original, and output paths, calls the existing public `decode()` unchanged, and writes a
single self-contained JSON object. Make the allocator measurement window visible in the
report so later analysis cannot mistake process setup for decode state.

### 3. GREEN: internal stage hooks

Add only the smallest internal hooks needed in `code/cubrim-rs/src/cm2.rs` and any
validated v2 dispatch helper. Preserve all existing error handling and wire checks. Do
not change the default function body or add an unconditional timing branch. Add tests
that compare default and profile-enabled round trips byte-for-byte.

### 4. GREEN: release runner

Add the Python runner and its tests. Build the normal and profile targets in release mode,
generate immutable profile inputs from the v2 manifest, and run the focused Rust/Python
tests. The runner must stop before writing a conclusion if any sample fails exactness,
the stage coverage contract, or the fixed-core verification.

### 5. REFACTOR and evidence

Keep the profiler code isolated and readable, remove only measurement-only duplication,
and rerun the relevant tests. Run the full v2 protocol, inspect the JSON against the
schema, calculate stage cycles/byte and time/byte from the recorded decoded-byte
denominator, and write the attribution report. The report must preserve negative or
inapplicable findings and must not call a stage `PASS` merely because it is zero.

## Verification gates

- Baseline and final default Rust tests pass in the available offline environment; the
  missing tracked `Cargo.lock` is recorded rather than hidden.
- Profile-enabled focused tests pass, and the separate release profiler builds.
- All 12/12 v2 samples decode byte-for-byte exactly under both affinity modes.
- Every sample has a persisted stage row with source/mode, calls, time/byte, cycles/byte
  or an explicit unavailable value, allocation metrics, and retained-state scope.
- The five above-64 KiB samples and seven below-64 KiB samples are visibly separated in
  the evidence table.
- The profile target is opt-in; the default target does not require the feature and
  `decode()` remains unchanged.
- `git diff --check`, focused tests, release builds, and the final worktree inspection
  pass; only owned files are staged. The shared backlog and foreign untracked files are
  left untouched.

## Deliverables

- `documentation/ephemeral/plans/CUBR-0075-profile-plan.md` (this plan);
- `code/cubrim-rs/src/decode_profile.rs`;
- `code/cubrim-rs/src/bin/cubrim_decode_profile.rs`;
- the minimal feature-gated internal hooks and Cargo target declaration;
- `bench/web-benchmark/profile_decode.py` and focused tests;
- `documentation/ephemeral/research/CUBR-0075-profile/attribution.json`; and
- `documentation/ephemeral/research/CUBR-0075-profile/attribution.md`.

If a required measurement cannot be made honestly, leave that criterion `BLOCKED` or
`PARTIAL`, journal the concrete reason, and do not advance the pending hypotheses.
