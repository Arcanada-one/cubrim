# CUBR packed Ctr zero-representation execution plan

**Goal:** Test whether XOR-biasing the packed `Ctr` probability makes its
midpoint initialization physically zero, reclaiming the page-commit RSS penalty
without surrendering PR41's decode-speed improvement or changing a single
archive byte.

**Design:** Keep the logical `Ctr` tuple unchanged. Store the upper 16-bit
probability as `t ^ (PSCALE / 2)`, so the initial logical midpoint is represented
by a zero word. Decode that bias on every probability read and encode it on every
probability write. The count and state bytes stay in their existing positions.

**Scope:** `code/cubrim-rs/src/cm2.rs`, focused tests in its existing test module,
this plan/preregistration, and a bounded evidence bundle. Do not touch
`decode()`, the wire format, encoder defaults, `cube_size_limit`,
`cm_should_try`, or `prof.rs` counters.

**Planning provenance:** The mandatory `coworker write --profile datarim-write`
first-draft call returned no output and created no target file. This native
fallback therefore supplies the audited plan; no empty delegate response was
accepted as evidence.

---

## Task 1: Land the preregistration before implementation or measurement

**Files**

- Verify: `documentation/ephemeral/research/CUBR-ZEROREP-20260808.md`
- Verify: `documentation/ephemeral/plans/CUBR-ZEROREP-20260808-plan.md`

1. Confirm the document records the 768 MiB packed-regression ceiling, the
   1,536 MiB total zero-word ceiling, the compound RSS/speed/identity prediction,
   the three pinned source/binary/input/archive identities, and the distinction
   between a void run and a complete negative result.
2. Run:

   ```bash
   git diff --check origin/main...HEAD
   git diff --name-only origin/main...HEAD
   git grep -nE 'decode\(|cube_size_limit|cm_should_try' origin/main...HEAD -- code || true
   ```

   Expected: only the two documentation files differ; no product code differs.
3. Commit the plan, push the preregistration branch, open a PR, wait for all
   applicable checks and review, then merge it normally. Do not measure first.
4. Fetch and verify the resulting `origin/main` contains the exact two landed
   document blobs. Record the resulting main SHA; it is the implementation base.

## Task 2: Create a fresh implementation worktree

1. Fetch the current remote and refuse a stale local base:

   ```bash
   git fetch origin main
   git rev-parse origin/main
   git status --short
   ```

2. Create a new branch and isolated worktree from that exact `origin/main`.
   Derive a collision-free worktree path and branch name at execution time; do
   not reuse the preregistration worktree or disturb any foreign worktree.
3. Re-read the landed preregistration and this plan from the new worktree before
   editing code.

## Task 3: Add focused RED tests

**File**

- Modify: `code/cubrim-rs/src/cm2.rs`

1. Add `ctr_zero_representation_starts_zero_and_predicts_midpoint` to the
   existing `#[cfg(test)] mod tests`:
   - construct a small `Ctr`;
   - assert every physical word in `v` is zero;
   - call `predict` on a slot and assert the logical stationary probability is
     `PSCALE / 2` and the returned history state is zero.
2. Add `ctr_zero_representation_update_preserves_logical_fields`:
   - construct a small `Ctr` and `build_nex()`;
   - obtain the initial state with `predict`, then perform one `upd`;
   - compute the expected logical probability with the existing `ctr_div`
     expression;
   - assert `predict` returns that logical probability and the expected next
     state;
   - assert the stored count byte is one and the physical probability field is
     the expected logical value XOR the bias.
3. Run only the two exact tests in release mode, one command per test:

   ```bash
   cd code/cubrim-rs
   cargo test --release --lib cm2::tests::ctr_zero_representation_starts_zero_and_predicts_midpoint -- --exact
   cargo test --release --lib cm2::tests::ctr_zero_representation_update_preserves_logical_fields -- --exact
   ```

   Expected RED: both fail against the current packed initializer/representation
   for the intended assertions. Preserve the failure output in the evidence log.

## Task 4: Implement the smallest XOR-bias representation

**File**

- Modify: `code/cubrim-rs/src/cm2.rs`

1. Introduce one private `u32` probability-bias constant equal to
   `(PSCALE / 2) as u32`.
2. Change `Ctr::new` to allocate `vec![0u32; 1usize << bits]`.
3. Decode the bias after extracting the upper 16 bits in both `Ctr::predict` and
   the `cur` read in `Ctr::upd`.
4. Encode the bias only when storing the updated `t` in the upper 16 bits. Leave
   the count byte, state byte, state-map behavior, indexing, and update formula
   unchanged. Prefer direct expressions or forced-inline private helpers; do not
   add a feature flag or another representation.
5. Re-run the two exact tests and require GREEN.
6. Run `cargo fmt --check` from `code/cubrim-rs`.

## Task 5: Prove the tests are mutation-sensitive

Use surgical temporary edits and restore each edit with another surgical patch;
never reset or check out paths.

1. Restore the old non-zero initializer temporarily. Require the initialization
   test to fail, then restore zero initialization and require it to pass.
2. Remove the read-side XOR temporarily. Require the midpoint test to fail, then
   restore it and require both focused tests to pass.
3. Remove the write-side XOR temporarily. Require the update test to fail, then
   restore it and require both focused tests to pass.
4. Save commands, exit codes, and the decisive assertion for each RED/GREEN pair.

## Task 6: Run product gates and audit forbidden surfaces

1. From `code/cubrim-rs`, run:

   ```bash
   cargo fmt --check
   cargo test --release
   cargo test --release --test scheme_roundtrip
   ```

   Record the actual library passed/failed/ignored counts and every integration
   suite result. Do not copy prior counts into the new evidence.
2. From the repository root, run:

   ```bash
   python -m pytest --strict-markers reproducibility/test_verify.py
   git diff --check origin/main...HEAD
   git diff --stat origin/main...HEAD
   git diff origin/main...HEAD -- code/cubrim-rs/src/cm2.rs
   git diff --name-only origin/main...HEAD
   ```

3. Inspect the code diff directly and prove that no excluded surface changed.
   Archive bytes must still be verified at runtime; source inspection alone is
   not output-identity evidence.

## Task 7: Build and pin all three comparison binaries

1. Use the preregistered source identities:
   - pre-PR41: `e70d1cdca6226e994c0393149e364f252f7c0a1f`;
   - current packed: `49e429e58722f730c4f3cbb0a69731fec430bb56`;
   - zero-rep: the reviewed implementation commit created by this plan.
2. On the measurement stand, use separate clean source/build directories. Build
   each with the same release command and toolchain. Verify the preregistered
   baseline/current binary SHA-256 values; derive and record the zero-rep binary
   SHA-256 after its build.
3. Verify the pinned `nci.2m` input SHA-256 and the existing canonical `nci/max`
   archive SHA-256 before generating any measurement.
4. Run the full release suite against the exact zero-rep source tree used for
   the candidate binary. A build from an untested tree is ineligible.

## Task 8: Commit a fail-closed runner before measurement

**File**

- Create: `documentation/ephemeral/research/CUBR-ZEROREP-20260808/zerorep-run.sh`

1. Encode the exact three source and binary hashes, input hash, canonical archive
   hash, file (`nci`), preset (`max`), CPU set (`0-15`), thread count (`4`), and
   output root into the runner. Derive the candidate hash and a new unique
   run-mode identifier at execution time; never fabricate them in advance.
2. Make the runner fail closed on load average >= 2.0, an existing Cubrim
   process, any hash mismatch, archive mismatch, warm-up failure, timeout, or
   `cmp` failure.
3. Generate one archive per build and require all three archives to match the
   canonical SHA-256 and each other before timed work.
4. Perform one unmeasured warm-up decode per build, then three measured decodes
   per build in interleaved order: pre-PR41, current-packed, zero-rep, repeated
   for samples 1 through 3.
5. Every decode must use `taskset -c 0-15`, four threads, `/usr/bin/time -v`, and
   the preregistered timeout. Verify `cmp` after every decode.
6. Emit raw logs, a machine-readable sample TSV, hashes, test evidence, and a
   terminal `DONE` marker only after all gates pass. Partial output is a void and
   goes to the stand journal only.
7. Shell-check the runner, commit it with the implementation, and obtain an
   independent review before execution. No runner edit is allowed after the first
   measured process starts.

## Task 9: Independent review before the live run

1. Give an isolated reviewer the mandate, preregistration, plan, code diff,
   focused/full test outputs, mutation proof, and runner.
2. Ask for findings only, prioritized Critical/Important/Minor, specifically on
   byte identity, logical equivalence, test sensitivity, hash pinning, fail-closed
   behavior, void semantics, DB semantics, and forbidden surfaces.
3. Resolve every Critical and Important finding. If any change affects the
   prediction or runner, recommit and re-review before measuring.

## Task 10: Execute the one-file experiment

1. Re-run the stand admission checks immediately before execution. Use the
   bounded systemd envelope from the preregistration; do not widen time, CPU,
   corpus, preset, repetitions, or restart a pinned campaign after a valid
   measured process begins.
2. Execute the committed runner exactly once for `nci/max`.
3. For a complete valid run, calculate per-build median wall time and peak RSS
   from the three samples. Report:
   - zero-rep RSS residual above pre-PR41;
   - bytes and percentage reclaimed from current packed;
   - reclaimed RSS as a fraction of the 768 MiB regression ceiling;
   - zero/current time ratio;
   - pre-PR41/zero speedup;
   - all archive and round-trip identities.
4. Judge each preregistered axis independently, then the compound prediction.
   Do not soften a failed threshold or tune a follow-up in this campaign.

## Task 11: Record a valid result or a void without conflating them

1. If the run is partial or any validity gate fails, write a void-journal entry
   with the exact failure and observed partial values. Add no DB rows, do not
   extend NEW-30, and do not claim a result.
2. If the run completes validly, insert exactly three median rows under the
   existing NEW-30 hypothesis using the new run mode, one per revision. Keep
   encode duration/RSS NULL and `evaluation = 0`; create no new hypothesis.
3. Extend NEW-30 with the compound verdict and per-file medians. Read back the
   rows through the DB/API/site surfaces required by the existing publication
   contract without exposing credentials.
4. If the prediction is refuted, preserve the negative result but remove the
   implementation from the deliverable; do not ship a speed trade-back. If it
   passes, keep the implementation eligible for integration.

## Task 12: Integrate only a passing lever and close on exact main

1. Produce the final evidence report and public-safe raw bundle, including exact
   commits, binary/input/archive hashes, full test counts, mutation proof,
   samples, medians, fractions of ceiling, DB row identities, and readbacks.
2. Run compliance/security checks appropriate to code plus a measurement-backed
   research result. Re-run the independent review if final code or runner changed.
3. For a passing lever only: push the implementation/evidence branch, open a PR,
   wait for terminal-success checks on the exact head SHA, obtain required review,
   and merge normally. For a refuted lever: open/merge only the evidence record,
   with no zero-rep product code.
4. Fetch `origin/main` after merge and verify:
   - local remote-tracking `origin/main` equals the actual remote head;
   - the landed source/evidence blobs equal the reviewed result;
   - applicable checks belong to the exact PR head/resulting main;
   - the three NEW-30 rows and publication readbacks remain present;
   - no forbidden surface changed.
5. Claim closure only after code/evidence, CI, resulting-main, DB, and publication
   proof are each explicit. Otherwise report the precise unclosed layer.
