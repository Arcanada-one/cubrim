# FU-01 — large-BWT implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` or `executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Test whether 256 KiB/1 MiB raw-byte BWT blocks close enough of the text gap to justify production integration.

**Architecture:** Preserve every v1 u16 BWT stream through checked wrappers and add an additive top-level mode 11 with u32 primary indexes. First expose it only through ignored forced tests; enter competitive-min only after the measured falsification checkpoint passes.

**Tech Stack:** Rust, existing SA-IS BWT, existing order-1 rANS, existing `cm_hash64`, Cargo tests.

---

- [x] **Step 0: Baseline integrity**  
  Run all existing BWT-related tests in `code/cubrim-rs`:
  ```bash
  cargo test --lib bwt
  ```
  Ensure all pass. Record commit SHA for later comparison.  
  Baseline observed before FU-01 edits: focused BWT tests pass. The complete
  library suite is 234 pass / 6 missing-corpus-fixture failures.

- [x] **Step 1: Generalise BWT core to `usize`**  
  In `code/cubrim-rs/src/codec.rs`:
  1. Locate the internal BWT encode and decode functions (the ones that return/accept a primary index).
  2. Change their primary-index type to `usize` (return for encode, argument for decode). Adjust internal array indexing and arithmetic to `usize`.
  3. Create two checked wrappers:
     - `bwt_encode_codes(…) -> u16` – calls the new `usize` encode, asserts `index <= u16::MAX`, returns `index as u16`.
     - `bwt_decode_codes(…, primary: u16, …)` – simply passes `primary as usize` to the new decode.
  4. All existing call sites of the old functions now call these wrappers.  
  Run all BWT tests – they must produce exactly the same bytes as before (cf. step 0).  
  *Commit: “bwt-core: generalize primary index to usize; retain u16 wrappers”*

- [x] **Step 2: New property tests for large BWT**  
  Add tests file (in existing test module) for the `usize` core round trips:
  - Local round-trip inputs of sizes:
    - 65 535 bytes (boundary)
    - 65 536 bytes (just over max u16)
    - 65 537 bytes
  - Add ignored dev-ai cases for 256 KiB and 1 MiB so DEVS is not used for
    heavy compression work.
  - Include periodic patterns (`AAAA…`), highly repetitive, and random adversarial data.
  - Each test: encode → decode, check equality; verify primary index is within `[0, raw_len)` and is `usize`-sized.
  Run these tests.  
  *Commit: “tests: property round-trips for large-BWT up to 1 MiB”*

- [x] **Step 3: Add private u32 large-BWT helpers**  
  In `code/cubrim-rs/src/codec.rs`:
  1. Create a private function `bwt_encode_large(…)` that:
     - calls the `usize` BWT core,
     - checks `primary_index <= u32::MAX`,
     - returns `raw_len: u32`, `primary_index: u32`, and the BWT-transformed data (byte array).
  2. Create a private function `bwt_decode_large(raw_len: u32, primary_index: u32, transformed: &[u8]) -> Vec<u8>` that:
     - converts arguments to `usize`,
     - calls the `usize` BWT decode.
  3. These will be used exclusively by mode 11.  
  Write unit tests: encode then decode with these helpers, verify byte-exact recovery.  
  *Commit: “codec: private u32 large-BWT encode/decode helpers”*

- [x] **Step 4: Define MODE_LARGEBWT = 11 and wire format**  
  In `code/cubrim-rs/src/header.rs`:
  1. Add constant `pub const MODE_LARGEBWT: u8 = 11;`.
  2. Keep the mode-specific parser private in `codec.rs`, matching the existing
     top-level container implementations; do not move codec logic into `header.rs`.
  3. Parse fields `orig_len: u64`, `block_size: u32`, `n_blocks: u32`, then each
     `[raw_len u32][primary u32][comp_len u32][raw_hash64 u64]` entry with checked arithmetic.
     - verifies MAGIC, VERSION, MODE bytes,
     - reads `orig_len`, `block_size`, `n_blocks`,
     - for each of `n_blocks`, reads `[raw_len, primary_index, comp_len, raw_hash64]`,
     - validates: `block_size > 0`, `n_blocks > 0`, `sum raw_len == orig_len`, `sum comp_len <= remaining payload`, every `primary_index < raw_len`,
     - returns the parsed header and a slice pointing to the start of concatenated rANS payloads.
  4. In `codec.rs`, add dispatch in the encoder: when mode is 11, use the `bwt_encode_large` helpers for each block, then apply order-1 rANS (the existing engine must be reusable). After rANS, write the concatenated payload.
  5. In the decoder: after parsing the header, for each block decode the rANS payload (should unify with existing rANS decode interface), verify `cm_hash64` of the decoded block equals `raw_hash64`, then apply `bwt_decode_large` to recover the block. Concatenate blocks. If any hash fails, return an error.
  6. Keep the encoder helper private and out of `encode_with_config_inner`; the
     decoder must support mode 11 immediately so forced artifacts are self-describing.
  *Commit: “header+codec: MODE_LARGEBWT=11 wire format and decode”*

- [x] **Step 5: Malformed-input tests**  
  Add tests that feed deliberately broken buffers to the mode-11 decoder:
  - Truncated header (missing blocks entirely, short block table)
  - `n_blocks = 0`
  - `primary_index >= raw_len` for a block
  - `sum raw_len != orig_len`
  - `comp_len` sum exceeds actual payload
  - rANS stream that decodes to a different length than expected
  - payload overflow (too many bytes read)
  - hash mismatch (flip one byte in rANS stream)
  For each, assert that the decoder returns an explicit error and does **not** produce any partial plaintext.  
  *Commit: “tests: malformed MODE_LARGEBWT headers and streams”*

- [x] **Step 6: Differential compatibility tests**  
  Keep `test_sais_bwt_matches_naive` and existing scheme-byte/golden tests green.
  Run `cargo test --lib bwt` and the differential fixtures that are present; do
  not fabricate absent corpus fixtures.
  *Commit: “tests: differential compatibility for u16 wrappers and old modes”*

- [x] **Step 7: Forced benchmark harness for dev-ai spike**  
  Create a dedicated test or binary that forces mode 11 on given input files. It must:
  - Read the file,
  - Compress with mode 11 using two candidate block sizes: `block_size = 256 * 1024` and `block_size = 1 * 1024 * 1024`.
  - For each, measure:
    - `compressed_bytes`
    - `ratio = compressed_bytes / original_bytes`
    - wall time (sequential, 1 thread)
    - peak RSS (if measurable)
    - Verify `RT=OK` and `cmp=0` (i.e., round-trip exact match, decompressed bytes equal original)
  - Run under `CUBR_THREADS=4`; candidates and files remain sequential.
  - Files: `plrabn12`, `alice29`, `asyoulik`, `webster` (paths in test data).
  - Output a CSV or structured log for later consumption.  
  *Commit: “bench: forced MODE_LARGEBWT spike harness (no claim of results)”*

- [ ] **Step 8: Execute spike on dev-ai**  
  Run the benchmark from Step 7 on the dev-ai machine:
  ```bash
  CUBR_THREADS=4 CUBR_FU01_CORPUS=/root/corpus-full \
    cargo test --release test_fu01_large_bwt_spike -- --ignored --nocapture
  ```
  Collect the data. Do **not** commit evaluated metrics in code, but record them for checkpoint decision.  
  *Checkpoint: does plrabn12 reach ratio ≤ 0.33?*

- [ ] **Step 9: Conditional – strict competitive rail & full-24**  
  **Only if** the checkpoint passes:
  1. In the competitive ranking logic: add mode 11 as a candidate, but only if the CM text-likeness detector flags the input (reuse existing detector, no new classifier). For non-text data, skip the BWT probe.
  2. Ensure the mode is considered only when its output is strictly smaller than the current winner (structural zero-per-file regression).
  3. Run the repository's established full-24 external runner sequentially on
     dev-ai with `CUBR_THREADS=4` and recalculate ranks from its JSON artifacts.
  4. Check that no file regresses (mode 11 is never selected if it doesn’t improve).  
  *Commit: “competitive: introduce MODE_LARGEBWT behind text-likeness gate, full-24”*

  If the checkpoint **fails**, do not continue with this step. Instead, document the failure and shift focus to IW-04/NEW-02 as per design.  
  *Commit (if needed): “reports: FU-01 checkpoint fail – no competitive integration”*

- [ ] **Step 10: Code review & cleanup**  
  - Ensure all new code is covered by tests (both unit and property).
  - Keep the forced spike test ignored; no production feature flag is needed.
  - Final commit message: “FU-01: large-BWT implementation ready for review”
