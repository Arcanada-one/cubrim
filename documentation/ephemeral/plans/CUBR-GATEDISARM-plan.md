# CUBR-GATEDISARM Profile-Independent BWT Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `executing-plans` to implement this plan task-by-task with review checkpoints.

**Goal:** Make the existing u16 BWT primary-index guard fail identically in debug and release while preserving the default production path, the wide-path test, and the v1 wire format.

**Architecture:** Keep `bwt_encode_codes_wide` and every decoder unchanged. Replace only the profile-dependent `debug_assert!` at the v1 u16 narrowing boundary with a profile-independent assertion, because the public encoder returns `Vec<u8>` rather than `Result` and the invalid `use_square_limit=false` path must remain an explicit hard failure instead of silently selecting a different scheme. Record the four-cell default/disabled debug/release evidence and the wire-format finding in an ephemeral journal.

**Tech Stack:** Rust/Cargo, Cubrim v1 codec, integration test corpus, debug and release profiles.

---

### Task 1: Establish the four-cell configuration matrix

**Files:**
- Read: `code/cubrim-rs/tests/scheme_roundtrip.rs`
- Create temporarily: `code/cubrim-rs/tests/gatedisarm_default_scratch.rs`
- Remove temporarily: `code/cubrim-rs/tests/gatedisarm_default_scratch.rs`

- [ ] **Step 1: Run the existing disabled-limit debug suite**

Run from `code/cubrim-rs`:

    cargo test --offline --test scheme_roundtrip

Expected baseline: `5 passed; 2 failed`; both BWT failures panic at `src/codec.rs:7028` with `primary_index 134980 exceeds u16::MAX`.

- [ ] **Step 2: Run the existing disabled-limit release suite**

Run:

    cargo test --offline --release --test scheme_roundtrip

Expected baseline: `7 passed; 0 failed`; this green result is the disarmed release gate caused by `debug_assert!` removal.

- [ ] **Step 3: Add a temporary default-limit matrix test**

Create `tests/gatedisarm_default_scratch.rs` with the same corpus loop and assertions as `scheme_roundtrip.rs`, but leave `EncodeConfig::v1_default().use_square_limit` unchanged. The two tests must call `assert_default_roundtrips(ValueScheme::BwtEntropy)` and `assert_default_roundtrips(ValueScheme::BwtGeoMix)`; the helper must read `../../bench/web-corpus/payloads-v2`, encode each payload with:

    let blob = cubrim::encode_with_config(&payload, &EncodeConfig {
        value_scheme: scheme,
        ..EncodeConfig::v1_default()
    });

and assert `cubrim::decode(&blob).expect("decode own output") == payload`.

- [ ] **Step 4: Run the default-limit scratch suite in debug and release**

Run both commands:

    cargo test --offline --test gatedisarm_default_scratch
    cargo test --offline --release --test gatedisarm_default_scratch

Expected result: both commands pass both tests. Remove the scratch file with the native patch tool after capturing the output; it is measurement scaffolding, not a shipped test.

### Task 2: Make the guard profile-independent

**Files:**
- Modify: `code/cubrim-rs/src/codec.rs:7026-7033`
- Test: `code/cubrim-rs/tests/scheme_roundtrip.rs`

- [ ] **Step 1: Replace only the profile-dependent assertion**

Change the `debug_assert!` at the narrowing boundary to `assert!`, preserving the condition and exact message:

    assert!(
        primary <= u16::MAX as usize,
        "primary_index {primary} exceeds u16::MAX; cube/chunk ceiling may have been raised above 65536 without updating BWT wire format"
    );

Do not change the return type, the cast, the wide BWT implementation, the decoder, the u16 wire field, or any configuration limit.

- [ ] **Step 2: Run the release disabled-limit suite after the guard change**

Run:

    cargo test --offline --release --test scheme_roundtrip

Expected result: the command now fails with `5 passed; 2 failed`, and the two failures carry the same `primary_index 134980 exceeds u16::MAX` assertion. This preserves the wide-path coverage and proves release no longer hides the defect.

### Task 3: Record the gate finding without changing the wire format

**Files:**
- Create: `documentation/ephemeral/research/CUBR-GATEDISARM.md`

- [ ] **Step 1: Write the evidence journal**

Record the four matrix outcomes, the exact failing assertion, the `use_square_limit=false` source semantics (`usize::MAX` versus default `65536`), the BWT-family blast radius, and the conclusion that widening `primary_index` is a separate wire-format decision. State explicitly that default debug/release pass and disabled debug/release fail after the guard repair.

- [ ] **Step 2: Verify the journal and scope**

Run:

    git diff --check
    git diff -- documentation/ephemeral/research/CUBR-GATEDISARM.md

Confirm the journal contains no DB measurements, campaign mutation, PR #28 changes, or claims of production corruption at defaults.

### Task 4: Verify, review, and deliver

**Files:**
- Verify: `code/cubrim-rs/src/codec.rs`
- Verify: `code/cubrim-rs/tests/scheme_roundtrip.rs`
- Verify: `documentation/ephemeral/research/CUBR-GATEDISARM.md`

- [ ] **Step 1: Run focused and source-wide checks**

Run:

    cargo fmt --all -- --check
    cargo test --offline --release --test scheme_roundtrip
    cargo test --offline --test scheme_roundtrip

The two scheme-roundtrip commands are expected to fail in both profiles after the guard is honest; record their exact counts rather than calling them green. Run focused codec/unit checks that do not exercise the intentionally invalid wide path separately and report any unrelated failure.

- [ ] **Step 2: Review the final diff**

Confirm only the guard line and the evidence journal are owned changes; `git diff --check` is clean; no wire format, DB, campaign, or PR #28 files changed.

- [ ] **Step 3: Commit and open a separate PR**

Commit the owned guard and journal with a focused message, push `codex/cubr-gatedisarm`, verify local HEAD equals its upstream SHA, and open a PR against `main`. Do not merge it. Leave the existing `CUBR-FUZZ-GAP` worktree and PR #28 untouched.
