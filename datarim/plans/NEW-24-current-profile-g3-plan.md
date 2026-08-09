# NEW-24 current-main attribution G3 implementation plan

**Goal:** prospectively instrument and run one current-main CM2 attribution
campaign without selecting or building a Fast-CM candidate.

**Architecture:** adapt the already validated G2 fail-closed runner to exact
source `e0e8bdb`, reduce it to three CM2 cells, add a second independent
record sample, and freeze a debug-line instruction map before sampling. Land
the instrument before launch; land raw evidence and the deterministic result
before any later candidate preregistration.

### Task 1: Land a self-contained prospective instrument

**Files:**

- `documentation/ephemeral/research/CUBR-NEW24-CURRENT-PROFILE-G3-20260809.md`
- `documentation/ephemeral/research/current-profile-g3-run.sh`
  `[to-be-created: campaign-specific fail-closed runner]`
- `documentation/ephemeral/research/current-profile-g3-run-test.sh`
  `[to-be-created: runner contract and mutation tests]`
- `documentation/ephemeral/research/current_profile_g3_map.py`
  `[to-be-created: deterministic instruction-address mapper]`
- `documentation/ephemeral/research/test_current_profile_g3_map.py`
  `[to-be-created: mapper unit and mutation tests]`

1. Write RED contract tests first. They must reject a missing runner and
   mapper, wrong three-cell set, any `x-ray` or `16-19` cell, wrong commit,
   altered archive/source hashes, pin drift, shortened timeouts, fewer than
   two encodes/one plain/two stat/two record decodes, absent `cmp`/SHA gates,
   missing map freeze/recheck, a restart/resume path, `Type=oneshot`, absent
   `.partial`/final ordering, or any DB/API/site operation.
2. Implement the mapper against synthetic decoded-line/disassembly fixtures.
   Unit tests cover unique mapping, overlap, gaps in targeted ranges,
   malformed addresses, PIE/ASLR normalization through exact DSO symbol
   offsets, deterministic ordering, and exact bucket-share reduction. A raw
   runtime virtual address must never be joined directly to an object-file
   offset. The join key comes from
   `objdump --disassemble --line-numbers`; its demangled variant is preserved
   separately for review because host perf retains Rust-v0 mangled symbols.
   The canonical unresolved `addr2line` sentinel `??:?` is non-target
   residual evidence. A target-owner instruction with an unresolved source
   line enters frozen `target_unresolved` and is never reassigned. Overlap or
   a dropped target address fails closed. Correlate raw/demangled symbol
   starts, retain every instruction in the compact `cubrim::cm2` symbol set,
   and store full transient disassembly hashes/counts instead of a full-binary
   instruction dump. Unknown offsets within retained CM2 symbols fail; exact-
   binary symbols outside that set reduce to `other_user`.
3. Adapt
   `documentation/ephemeral/research/decode-attrib-run.sh` rather than
   rewriting its admission, timeout, manifest, source/corpus, side-effect
   cleanup, and round-trip machinery. Use exact
   paths unique to G3, exact `e0e8bdb`, the three registered cells and their
   original timeouts, five verified decodes per cell, two independent record
   data files, and the 14,400-second monotonic budget.
4. Remove G2's test overlay: current main owns its tests. Capture and remove
   the generated Cargo lock and target outputs so the detached tracked source
   returns clean. Run `cargo test --release` and
   `cargo test --release --test scheme_roundtrip -- --nocapture` before any
   cell.
5. Build once with release code generation and line debug information. The
   operator supplies the reviewed runner SHA at launch; the runner verifies
   its own bytes, source, binary, mapper, generated map, toolchain, and
   manifest before performance work.
6. Add mutation tests for every hard-coded cell/hash/timeout, runner/binary
   authentication, source-line bucket boundary, 10% cycle threshold, 1.10 G3
   threshold, 1-point share threshold, independently marked target-owner
   coverage plus runner/mapper schema integration, `target_unresolved`, zero
   lost samples, `N_eff >= 4787`, simultaneous
   95%-bound `U <= 0.001`, `TIMING-DONE.STAMP` ordering, and the no-resume/no-
   restart contract.
7. Run `bash -n`, ShellCheck, Python unit tests, runner contract tests, all
   repository tests touched by the instrument, `git diff --check`, and an
   owned-path secret scan.
8. Give the exact commit to separate read-only spec and quality subagents.
   Resolve every Critical/Important finding, re-run checks, push a normal PR,
   wait for terminal success on the exact head, merge without bypass, fetch,
   and verify exact current-main tree parity.

### Task 2: Feasibility and authenticated launch

1. On `dev-ai`, create a new detached checkout at `e0e8bdb`; refuse any
   existing checkout, binary, output, or unit path for this campaign.
2. Copy the exact mainline runner and mapper, verify their hashes, and build
   the debug-line release binary in a campaign-specific target directory.
   Run admission-only/self-test mode; it may build/map/smoke but must not
   encode or decode a corpus cell.
3. Prove the binary has decoded line information and the mapper uniquely
   covers the targeted production regions. Before any corpus-cell encode,
   construct exactly 65,536 zero bytes with `/usr/bin/dd`, require source
   SHA-256 `de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31`,
   encode it twice at preset `max`, and require both archives plus their byte
   comparison to match SHA-256
   `352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3`
   (50 bytes). Decode once and byte-compare the restored fixture. This exact
   e0e8bdb identity was fixed before launch; do not read or report performance
   values.
4. Freeze binary, generated lock, map, runner, mapper, toolchain, code, corpus,
   topology, and invocation identities in the pre-sample journal. Make copied
   instruments read-only.
5. Launch once with `systemd-run --service-type=exec`, `Restart=no`, and
   `RuntimeMaxSec=4h5m`. The command must invoke the reviewed runner via an
   absolute `/usr/bin/bash` and pass the reviewed hashes. Record the systemd
   invocation ID. Never restart a failed or interrupted campaign.
6. Monitor read-only until terminal. Validate exit/result, `NRestarts=0`,
   timestamps, effective runtime cap, no orphan processes, final-versus-
   partial exclusivity, done-stamp ordering, tree types/modes, and exhaustive
   hashes before reading performance values.

### Task 3: Deterministic result and current ceiling

**Files created only after a terminal valid run:**

- `documentation/ephemeral/research/CUBR-NEW24-CURRENT-PROFILE-G3-RESULTS-20260809.md`
  `[to-be-created: only after a terminal valid run]`
- `documentation/ephemeral/research/CUBR-NEW24-CURRENT-PROFILE-G3-RESULTS-20260809/`
  `[to-be-created: byte-exact raw evidence only after a terminal valid run]`

1. Copy the raw tree byte-for-byte into an isolated result worktree and
   verify source/destination manifests and path exhaustiveness before parsing.
2. Write a deterministic parser and RED tests for all admission/correctness
   gates, cycle disagreement, G3 ratios, unique instruction mapping, two-run
   bucket stability, P1–P5, and void/no-select routing.
3. Report both raw samples and within-file reductions only. Compute a
   perfect-component Amdahl ceiling per bucket per file. Never compute a
   corpus aggregate, geometric mean, MiB/s, or inferred miss-stall share.
4. Independently reconcile raw-to-parser-to-report with separate spec and
   quality subagents. The report may declare a bucket eligible for later
   selection but may not select or implement a lever.
5. Commit the raw tree, parser, tests, outputs, and report; run all manifests,
   parser drift checks, secret scan, and full relevant tests. Land through a
   normal exact-head PR and verify resulting current `origin/main` blob parity.
6. Only after the report lands, prepare a separately reviewed idempotent DB
   transaction that appends one pointer while preserving NEW-24
   `in_progress`, zero measurements, zero evaluation, and no web-benchmark
   hypothesis row. Backup, apply once, replay (`UPDATE 0`), fresh-process
   readback, and land the transaction evidence through another protected PR.

### Task 4: Route after the result

- If P2/P3/P5 support a material StateMap bucket, independently select and
  preregister SM32 or another single bounded lever with a new current ceiling.
- If StateMap is below 5% or attribution is ambiguous, record `NO-SELECT` for
  SM32. Consider another distinct current bucket only from the landed G3
  evidence.
- In either case, no candidate source exists before its own preregistration is
  merged to current `main`.

## Path validation

`PATH VALIDATION` (2026-08-09): checked 10 concrete filesystem paths. Present
in this worktree/host: the preregistration, the G2 runner, and
`/usr/bin/bash`. `/root/phaseC/corpus_manifest.tsv` is an external `dev-ai`
runtime prerequisite and remains an admission check, not a local existence
claim. The four instrument paths are explicitly
`[to-be-created]` in Task 1; the two result paths are explicitly
`[to-be-created]` only after a terminal valid run. No present repository path
has a documented deprecation marker. `origin/main` is a Git revision, not a
filesystem path.
