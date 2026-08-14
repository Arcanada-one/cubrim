# CUBR-0075 Allocation Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` (recommended, when your runtime supports spawning isolated agents) or `executing-plans` (single-session execution) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the registered CUBR-0075 bounded-state criteria with an opt-in native Web Profile decoder probe and content-addressed evidence, without changing the default decoder or publishing database rows.

**Architecture:** A feature-gated Rust example in `cubrim-web-decoder` constructs the canonical static/dynamic frames, drives the existing native stream ABI, and records counting-global-allocator observations with explicit input/output/decoder scope. A Python admission/provenance wrapper builds and runs that probe under the existing singleton-CPU protocol, validates the JSON bundle, and writes a journal-only local evidence report.

**Tech Stack:** Rust 2021, Cargo feature-gated example, `cubrim-web-decoder` native C ABI, `serde`/`serde_json`, `sha2`, Python 3 `unittest`, `taskset`, existing web-corpus manifest.

---

## File map

- Modify `code/cubrim-web-decoder/Cargo.toml`: add the opt-in feature,
  example target, and benchmark-only dev dependencies.
- Create `code/cubrim-web-decoder/examples/allocator_telemetry_probe.rs`:
  deterministic frame construction, counting allocator, native ABI driving,
  exact round-trip checks, and JSON output.
- Create `bench/web-benchmark/allocator_telemetry_runner.py`: host admission,
  clean-tree/provenance checks, singleton-CPU execution, journal handling, and
  bundle validation.
- Create `bench/web-benchmark/tests/test_allocator_telemetry_runner.py`:
  focused schema/cardinality/provenance/void tests using deterministic fakes.
- Create `documentation/ephemeral/research/CUBR-0075-ALLOCATOR-TELEMETRY-PREREG-20260814.md`:
  frozen protocol and thresholds; no measured values.
- Create `documentation/ephemeral/research/CUBR-0075-ALLOCATOR-TELEMETRY-RESULT-20260814.md`
  only after a valid measurement; it records evidence and residual boundaries.

No API, site, database, public, upstream, or root-workspace files are touched
in this plan.

## Task 1: Freeze the telemetry contract and write failing tests

**Files:**

- Create: `documentation/ephemeral/research/CUBR-0075-ALLOCATOR-TELEMETRY-PREREG-20260814.md`
- Create: `bench/web-benchmark/tests/test_allocator_telemetry_runner.py`

- [ ] **Step 1: Write the frozen preregistration.** Record exactly 13
  `manifest.v3` samples, static and dynamic profiles, three warmups, 30
  measured trials, seed `75075`, block/chunk size `65536`, exact SHA/byte
  round trips, singleton-CPU admission, journal-only voids, and these frozen
  criteria:

  ```text
  WIN largest_single_allocation_bytes <= 65536
  GO  largest_single_allocation_bytes <= 4194304
  GO  auxiliary_memory_bound_ratio <= 1
  ```

  State that allocator instrumentation perturbs timing and that no timing
  conclusion, database write, public release, or upstream action is part of
  this slice.

- [ ] **Step 2: Write runner tests before implementation.** The tests must
  import the runner through `importlib` and cover exact behavior, not merely
  import success:

  ```python
  def test_validate_bundle_requires_13_samples_and_30_trials(self):
      bundle = fixture_bundle(samples=13, trials=30)
      self.assertEqual(validate_bundle(bundle), bundle)
      with self.assertRaises(MeasurementVoid):
          validate_bundle(fixture_bundle(samples=12, trials=30))
      with self.assertRaises(MeasurementVoid):
          validate_bundle(fixture_bundle(samples=13, trials=29))

  def test_validate_bundle_rejects_roundtrip_or_provenance_drift(self):
      bundle = fixture_bundle()
      bundle["results"][0]["roundtrip_exact"] = False
      with self.assertRaises(MeasurementVoid):
          validate_bundle(bundle)
      bundle = fixture_bundle()
      bundle["provenance"]["source_sha"] = "drift"
      with self.assertRaises(MeasurementVoid):
          validate_bundle(bundle, expected_source_sha="expected")

  def test_criterion_result_is_derived_from_raw_rows(self):
      bundle = fixture_bundle(largest=4096, auxiliary_ratio=0.25)
      result = summarize(bundle)
      self.assertEqual(result["decision"], "GO")
      bundle = fixture_bundle(largest=4194305, auxiliary_ratio=0.25)
      self.assertEqual(summarize(bundle)["decision"], "NO_GO")
  ```

- [ ] **Step 3: Run the tests and verify the expected RED state.**

  ```bash
  python3 -m unittest -v bench/web-benchmark/tests/test_allocator_telemetry_runner.py
  ```

  Expected: collection fails because `allocator_telemetry_runner.py` and its
  contract functions do not yet exist. Do not treat the missing module as a
  measurement void.

- [ ] **Step 4: Commit the contract and RED tests.**

  ```bash
  git add documentation/ephemeral/research/CUBR-0075-ALLOCATOR-TELEMETRY-PREREG-20260814.md \
          bench/web-benchmark/tests/test_allocator_telemetry_runner.py
  git commit -m "test: freeze CUBR-0075 allocator telemetry contract"
  ```

## Task 2: Add the opt-in Rust probe and allocator accounting

**Files:**

- Modify: `code/cubrim-web-decoder/Cargo.toml`
- Create: `code/cubrim-web-decoder/examples/allocator_telemetry_probe.rs`

- [ ] **Step 1: Add feature and benchmark-only dependencies.** Keep the
  library's default feature set empty and make the example require the opt-in
  feature:

  ```toml
  [features]
  allocator-telemetry = []

  [[example]]
  name = "allocator_telemetry_probe"
  required-features = ["allocator-telemetry"]

  [dev-dependencies]
  cubrim = { path = "../cubrim-rs" }
  serde = { version = "1", features = ["derive"] }
  serde_json = "1"
  sha2 = "0.10"
  ```

- [ ] **Step 2: Implement the counting allocator with no allocation in its
  hooks.** Use `std::alloc::System`, atomics, and a thread-local recursion
  guard. `alloc`, successful `realloc`, and `dealloc` update event totals;
  `current_live` is tracked with saturating arithmetic; a snapshot captures
  baseline live bytes, peak live delta, largest request, and event counts.
  A failed allocation is never counted as a successful observation.

  ```rust
  #[global_allocator]
  static ALLOCATOR: CountingAllocator = CountingAllocator;

  #[derive(Clone, Copy, Debug, Serialize)]
  struct AllocationSnapshot {
      allocation_count: u64,
      allocated_bytes: u64,
      deallocated_bytes: u64,
      peak_live_bytes: u64,
      largest_single_allocation_bytes: u64,
      live_bytes_after: u64,
  }
  ```

- [ ] **Step 3: Implement deterministic manifest/frame setup.** Deserialize
  `schema_version=2`, read each sample relative to the manifest, verify byte
  count and SHA-256, construct static frames with `EncodeConfig::web_profile`
  and dynamic frames with `cubrim::encode_web_dynamic`, and verify both with
  the existing `cubrim::decode`. Persist frame mode and frame SHA in the
  output; reject any mode other than `web` or the explicitly recorded
  `raw_store` mode.

- [ ] **Step 4: Implement the ABI measurement loop.** For each of 13 samples
  and both profiles, run exactly three warmups, then exactly 30 randomized
  trials. Reset allocator counters immediately before constructing the stream
  handle; feed the immutable frame in chunks of at most `65536` bytes through
  `cbm_stream_push`; record the maximum `cbm_stream_memory_usage` value; call
  `cbm_stream_finish`; copy no fresh output; verify `cbm_stream_error_*` is
  empty on success; drop/free all owned objects; and capture the post-drop
  snapshot.

  ```rust
  let handle = unsafe {
      cbm_stream_new_with_limits(
          DecodeLimits::DEFAULT_MAX_OUTPUT,
          DecodeLimits::DEFAULT_MAX_EXPANSION_RATIO,
          DecodeLimits::DEFAULT_MAX_DECODER_MEMORY,
      )
  };
  for chunk in frame.chunks(65_536) {
      let ok = unsafe { cbm_stream_push(handle, chunk.as_ptr(), chunk.len()) };
      if ok == 0 { return Err(void_from_ffi(handle)); }
      peak_decoder_bytes = peak_decoder_bytes.max(unsafe {
          cbm_stream_memory_usage(handle)
      });
  }
  let finished = unsafe { cbm_stream_finish(handle) };
  if finished == 0 { return Err(void_from_ffi(handle)); }
  unsafe { cbm_stream_free(handle); }
  ```

  Derive `auxiliary_peak_bytes` as the conservative decoder-owned peak minus
  the known input frame bytes and declared output bytes, saturating at zero;
  persist all three operands and compute
  `auxiliary_memory_bound_ratio = auxiliary_peak_bytes / frame_bytes`.
  This is an explicit capacity upper-bound metric, not RSS.

- [ ] **Step 5: Emit a schema-versioned JSON bundle.** Require provenance,
  protocol counts, environment, raw trial rows, aggregate maxima, and a
  derived `decision` only when every cell is valid. On any trial error, print
  a journal-only `VOID` record and exit non-zero without emitting a valid
  bundle.

- [ ] **Step 6: Add focused Rust tests and run them.** Test allocator reset,
  successful allocation/reallocation/deallocation accounting, exact frame
  round trips through the probe helper, and overflow/recursion handling.

  ```bash
  cargo test --manifest-path code/cubrim-web-decoder/Cargo.toml --all-targets
  cargo test --manifest-path code/cubrim-web-decoder/Cargo.toml \
    --features allocator-telemetry --example allocator_telemetry_probe
  ```

- [ ] **Step 7: Commit the probe after focused tests pass.**

  ```bash
  git add code/cubrim-web-decoder/Cargo.toml \
          code/cubrim-web-decoder/examples/allocator_telemetry_probe.rs
  git commit -m "feat: add opt-in CUBR-0075 allocator probe"
  ```

## Task 3: Add the admission/provenance runner

**Files:**

- Create: `bench/web-benchmark/allocator_telemetry_runner.py`
- Modify: `bench/web-benchmark/tests/test_allocator_telemetry_runner.py`

- [ ] **Step 1: Implement fail-closed validation helpers.** The runner must
  expose `MeasurementVoid`, `validate_bundle(bundle, expected_source_sha=None)`,
  and `summarize(bundle)`. Validate exact schema version, task/phase, sample
  set, 2 profiles, 30 trials/profile, exact round trips, non-empty hashes,
  allocator non-negative integers, ratio operands, and decision derivation.
  Reject missing or extra samples rather than silently aggregating a subset.

- [ ] **Step 2: Implement host admission and singleton execution.** Reuse the
  repository's thermal/load conventions; require one effective CPU, load per
  CPU at or below `1.0`, available temperature below `90 C`, and `taskset` for
  a non-singleton parent mask. Record hostname, kernel, Python/Rust versions,
  CPU topology, affinity, load, and temperature in the journal. Recheck
  admission before invoking the probe and after it returns.

- [ ] **Step 3: Implement provenance and clean-tree gates.** Bind the current
  Cubrim source SHA, runner SHA, probe SHA, binary SHA, and manifest SHA. Refuse
  a dirty worktree, unexpected branch head, missing manifest, or mismatched
  probe output. Write only the requested evidence path and journal path.

- [ ] **Step 4: Add runner tests for command construction and voids.** Extend
  the test file with deterministic fakes for `taskset`, temperature/load
  readers, subprocess output, dirty-tree refusal, source-hash mismatch,
  admission lapse, and a valid 780-cell bundle.

- [ ] **Step 5: Run the Python focused suite.**

  ```bash
  python3 -m unittest -v bench/web-benchmark/tests/test_allocator_telemetry_runner.py
  ```

  Expected: all contract, schema, provenance, and fail-closed tests pass.

- [ ] **Step 6: Commit the runner and tests.**

  ```bash
  git add bench/web-benchmark/allocator_telemetry_runner.py \
          bench/web-benchmark/tests/test_allocator_telemetry_runner.py
  git commit -m "feat: add CUBR-0075 allocator telemetry runner"
  ```

## Task 4: Build and execute the measurement

**Files:**

- Create locally under `/home/dev/evidence/CUBR-0075-ALLOCATOR-TELEMETRY-20260814/`:
  `allocator-telemetry.json`, `journal.jsonl`, and any void logs.
- Create only after a valid run in the repo:
  `documentation/ephemeral/research/CUBR-0075-ALLOCATOR-TELEMETRY-RESULT-20260814.md`.

- [ ] **Step 1: Build the exact feature-enabled release probe from a clean
  exact-main branch.**

  ```bash
  cargo build --release --manifest-path code/cubrim-web-decoder/Cargo.toml \
    --example allocator_telemetry_probe --features allocator-telemetry
  sha256sum code/cubrim-web-decoder/target/release/examples/allocator_telemetry_probe
  git rev-parse HEAD
  sha256sum bench/web-corpus/manifest.v3.json
  ```

- [ ] **Step 2: Run the focused runner on an admitted host.**

  ```bash
  python3 bench/web-benchmark/allocator_telemetry_runner.py \
    --manifest bench/web-corpus/manifest.v3.json \
    --probe code/cubrim-web-decoder/target/release/examples/allocator_telemetry_probe \
    --out /home/dev/evidence/CUBR-0075-ALLOCATOR-TELEMETRY-20260814/allocator-telemetry.json \
    --journal /home/dev/evidence/CUBR-0075-ALLOCATOR-TELEMETRY-20260814/journal.jsonl
  ```

  Expected: one schema-valid bundle with `780` valid cells, exact round trips,
  and a derived decision. If the host fails admission, retain the journal-only
  void and re-run on a currently admitted internal host; do not turn it into a
  threshold result.

- [ ] **Step 3: Independently validate raw output.** Recompute all SHA-256
  values, trial cardinality, maximum allocation, maximum auxiliary ratio,
  and decision from the raw rows with a second read-only command. Require the
  recomputed values to match the probe and runner output byte-for-byte where
  the schema promises deterministic fields.

- [ ] **Step 4: Write the result report only after valid evidence.** State the
  exact decision and metrics, distinguish `NO_GO` from protocol void, include
  bundle/journal/probe/manifest/source hashes, and list remaining unmeasured
  boundaries. Do not write API/DB rows in this task.

- [ ] **Step 5: Commit the result report and evidence pointer.**

  ```bash
  git --no-pager diff --check
  git add documentation/ephemeral/research/CUBR-0075-ALLOCATOR-TELEMETRY-RESULT-20260814.md
  git commit -m "docs: record CUBR-0075 allocator telemetry result"
  ```

## Task 5: Final verification and delivery

- [ ] **Step 1: Run the default decoder regression suite with the feature off.**

  ```bash
  cargo test --manifest-path code/cubrim-web-decoder/Cargo.toml --all-targets
  python3 -m unittest -v bench/web-benchmark/tests/test_allocator_telemetry_runner.py
  git --no-pager diff --check
  ```

- [ ] **Step 2: Confirm default behavior is unchanged.** Build the decoder
  library without `allocator-telemetry`, inspect `git diff --stat`, and verify
  no public API, wire-format, API/site, database, or root-workspace file was
  changed. The telemetry example must not build unless the feature is named.

- [ ] **Step 3: Push the branch and open an internal PR.** Use the exact branch
  `cubr-0075-telemetry-20260814`, wait for all repository checks, and merge only
  after green. The result remains internal evidence; no public/upstream action
  is permitted by this plan.

- [ ] **Step 4: Fetch and verify current `origin/main`.** Prove the landed
  report blob SHA matches the branch content after squash merge, and verify the
  exact current main before reporting completion or any residual boundary.

## Self-review

- Coverage: the preregistration freezes protocol/thresholds; Tasks 2–3 provide
  probe/schema/runner; Task 4 produces only valid local evidence; Task 5 covers
  regression and exact-main delivery.
- No placeholders: every file, command, criterion, and void condition is
  specified above.
- Type consistency: `MeasurementVoid`, `validate_bundle`, `summarize`,
  `allocator-telemetry`, `allocator_telemetry_probe`, and the JSON field names
  are used consistently across tests, probe, runner, and report.
- Scope: database/API publication is intentionally a later guarded slice,
  separate from this measurement-only plan.
