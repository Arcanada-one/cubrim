# NEW-24 Current-Profile G6 Implementation Plan

> **Execution rule:** implement task by task with `subagent-driven-development`.
> Every implementation handoff requires a fresh specification review followed
> by a fresh quality review of the exact bytes being proposed.

**Goal:** Preserve G5 as an immutable pre-sampling `VOID`, preregister G6 as a
new experiment, build the frozen binary twice from independent source trees,
run one no-performance admission, land a concrete protected campaign identity
set, execute one campaign, and publish a terminal per-file result without a
database, API, site, social, credential, or source-selection mutation.

**Architecture:** G6 has four irreversible one-shot transitions: prebuild,
validation, admission service, and campaign service. The prebuild creates two
independent source/target pairs and a receipt; validation proves the exact
suites in a separate checkout/target; admission authenticates both seals and
freezes the static map without interpreting performance; the campaign consumes
that exact admission seal. A failure never authorizes a retry under G6. No G5
runtime path or artifact content is an input. The only G5 provenance inputs are
the incident-record blob; incident-manifest blob, SHA-256, and bytes; raw
journal SHA-256 and bytes; canonical-journal blob, SHA-256, and bytes; and the
controlling-preregistration blob, reviewed head, and resulting-main commit.

**Frozen scientific identities:**

- source commit: `830a9a31deb00926a97f3fa5bd74f58003573fc0`
- Rust/Cargo: `1.96.1`; rustc commit
  `31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd`
- generated `Cargo.lock` SHA-256:
  `0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9`
- release binary SHA-256:
  `2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78`
- ELF build ID: `789119db24ae1a28a24bcc0ecbec136c7e937d9a`
- G5 incident manifest: 261 bytes,
  `2d8cbdf7876644a69e176e9578c2b663a12ebe1872ecb1a1048b72c77eb99b15`
- retained G5 incident-manifest blob:
  `49fb705f5230a35e43726d4f6a333e47c5cb1b29`
- G5 unit journal: 6428 bytes, raw incident capture
  `b11d33ecde790f61e679494d9e48419688a1aef0e3a979de2eb5b65556597c25`;
  compact sorted-key canonical render
  `926fdebe5690ce450ce6970c3260c54ce37bd095241f760d2acd9931b0586e4c`
- retained canonical journal blob:
  `5ea61262dacd442fdf1676a7a7613c8e5534b6a3`
- controlling G5 preregistration:
  `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md`,
  blob `5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f`, reviewed head
  `e4f7efe84d6478d5f0c7286873910972f87b4d68`, resulting main
  `c498c0560b6c25c1cf0327ec809cefbf4dbe0dd4`
- reviewed G5 source-code fork inputs: runner
  `a2aff453bc0b8049172776452cd5e8c5b84811ff`, runner test
  `8d1072b74a3429985ba1bd0db78601a3be144743`, mapper
  `0bbdf7d903bf43ab288ba2808b77e6dc36ea5461`, mapper test
  `b62d7f8d9985e5ad49926a6d3182c3fd79632b41`

## Task 0: Land the prospective protocol

**Owned files:**

- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811.md`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/systemd-journal.canonical.jsonl`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/remote-tree-manifest.tsv`
- `documentation/ephemeral/reviews/CUBR-NEW24-G5-ADMISSION-CONSILIUM-20260811.md`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-20260811.md`
- `datarim/plans/NEW-24-current-profile-g6-plan.md`

- [ ] Re-fetch `origin/main` and prove local `origin/main` equals
  `git ls-remote origin refs/heads/main`.
- [ ] Reauthenticate the controlling G5 preregistration path/blob, reviewed
  head, resulting-main ancestry, and exact lines 507–513 before using its
  no-retry/new-protocol authority.
- [ ] Reauthenticate the G5 unit on `dev-ai` as
  `LoadState=loaded`, `ActiveState=failed`, `SubState=failed`,
  `Result=exit-code`, `ExecMainStatus=1`, `NRestarts=0`, and
  `InvocationID=9bb2c1d32c714cf28575e61fcbb601bc`.
- [ ] Prove `cubr-new24-full-binary-g5-20260810.service` is `not-found`, every
  G5 campaign output variant is absent, and the only admission output is the
  sealed `.partial` incident tree.
- [ ] Recompute the canonical G5 incident manifest and canonical unit JSON
  journal. Do not compare a fresh nondeterministically key-ordered raw render
  with the historical raw-capture hash. Select only
  `cubr-new24-full-binary-g5-admission-20260810.service`, parse every JSON
  event, sort events by `__CURSOR`, sort each event's keys, serialize with
  compact separators and one newline, and require exactly 6428 bytes and
  SHA-256
  `926fdebe5690ce450ce6970c3260c54ce37bd095241f760d2acd9931b0586e4c`.
  Compare those bytes with the retained JSONL file and require its Git blob
  `5ea61262dacd442fdf1676a7a7613c8e5534b6a3`.
- [ ] Compare the recomputed 261-byte incident-manifest stream byte-for-byte
  with the retained TSV and require Git blob
  `49fb705f5230a35e43726d4f6a333e47c5cb1b29`.
- [ ] Run `git diff --check` and a forbidden-marker scan assembled so it does
  not match its own expression:

  ```bash
  marker_a='TO'; marker_b='DO'; marker_c='<filled'; marker_d='after'
  marker_e='boiler'; marker_f='plate'
  ! rg -n "${marker_a}${marker_b}|T[B]D|${marker_c} ${marker_d}|mirror G[45]|same as G[45]|${marker_e}${marker_f}" \
    documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811.md \
    documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/systemd-journal.canonical.jsonl \
    documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/remote-tree-manifest.tsv \
    documentation/ephemeral/reviews/CUBR-NEW24-G5-ADMISSION-CONSILIUM-20260811.md \
    documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-20260811.md \
    datarim/plans/NEW-24-current-profile-g6-plan.md
  ```

- [ ] Record `git hash-object` for all six paths. Obtain independent
  specification and quality approvals for exactly those blobs.
- [ ] Force-add only the ignored plan and normally add the other five paths;
  commit, push, and open one six-path PR.
- [ ] Require terminal-success CI on the exact reviewed PR head, merge
  normally, fetch `origin/main`, and prove reviewed-head ancestry plus
  resulting-main blob parity for all six paths.
- [ ] Record that resulting main as `CUBR_NEW24_G6_BASELINE`. No G6 source,
  target, receipt, unit, or output path may exist before this point.

## Task 1: Establish G6 instrument contracts under RED

**New files:**

- `documentation/ephemeral/research/current-profile-g6-run.sh`
- `documentation/ephemeral/research/current-profile-g6-run-test.sh`
- `documentation/ephemeral/research/current_profile_g6_map.py`
- `documentation/ephemeral/research/test_current_profile_g6_map.py`
- `documentation/ephemeral/research/current-profile-g6-prebuild.sh`
- `documentation/ephemeral/research/current-profile-g6-prebuild-test.sh`
- `documentation/ephemeral/research/current-profile-g6-validate.sh`
- `documentation/ephemeral/research/current-profile-g6-validate-test.sh`

- [ ] Create a clean isolated `codex/cubr-new24-g6-instrument` worktree from
  the fresh baseline. Recompute and require the four frozen G5 source-code
  input blobs above from `origin/main`; do not encode future G6 blobs in this
  plan.
- [ ] Copy the G5 runner, runner test, mapper, and mapper test into the four
  G6 paths. Keep shell assets executable and Python assets mode `0644`.
  Assert the four G5 source blobs remain unchanged.
- [ ] Add failing G6 namespace tests before editing production code. They must
  require literal source roots `/root/cubr-new24-full-binary-g6-src-a` and
  `/root/cubr-new24-full-binary-g6-src-b`, target roots
  `/root/cubr-new24-full-binary-g6-target-a` and
  `/root/cubr-new24-full-binary-g6-target-b`, receipt root
  `/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811`, validation source
  `/root/cubr-new24-full-binary-g6-validation-src`, validation target
  `/root/cubr-new24-full-binary-g6-validation-target`, output
  `/root/cubr-new24-full-binary-g6-validation-20260811`, external validation
  manifest roots
  `/root/cubr-new24-full-binary-g6-validation-manifest-20260811` and
  `/root/cubr-new24-full-binary-g6-validation-manifest-20260811.partial`,
  instrument root
  `/root/cubr-new24-full-binary-g6-instrument`, admission input
  `/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env`, admission root
  `/root/cubr-new24-full-binary-g6-map-dryrun-20260811`, campaign root
  `/root/cubr-new24-full-binary-g6-20260811`, both exact service names, and
  `cubr-new24-g6-*` mapper schemas. Tests must reject every G5 runtime namespace and
  `config/credentials/`.
- [ ] Add failing prebuild behavior tests. The production helper does not yet
  exist, so the contract suite itself must exit nonzero; a test that accepts a
  stub message as success is forbidden.
- [ ] Capture the RED output, then implement only the mechanical G6 namespace
  split needed to make the namespace tests green. Do not add service launch or
  performance behavior in this task.
- [ ] Mutation-check namespace tests by restoring one G5 unit literal, one G5
  path literal, and one G5 schema literal in temporary copies. Each mutation
  must fail for the intended assertion.

## Task 2: Implement and verify the one-shot prebuild

The prebuild helper is directly executable only in production mode. Its test
mode uses an explicit `CUBR_G6_TEST_MODE=1` seam and injected command directory;
production mode rejects all identity/path overrides.

- [ ] Build a sandboxed test harness using `mktemp -d` and mock `git`, `cargo`,
  `taskset`, `cmp`, `readelf`, `sha256sum`, `find`, `stat`, `chmod`, and
  `systemctl` commands. The
  harness must prove all of these observable behaviors:

  1. every source, target, receipt, `.partial`, and final-path collision fails
     before a clone;
  2. a symlink at any owned path fails closed;
  3. the manifest contains exactly one root-directory row with an empty
     relative path; any nested symlink, FIFO, socket, device,
     non-ASCII/control-character path, or non-root path outside
     `^[A-Za-z0-9._/@+=,-]+$` fails before manifesting;
  4. two `git clone --no-local --no-checkout` calls create separate object
     stores and both detach at the frozen source commit;
  5. both trees are clean before lock generation;
  6. lock generation runs independently in both trees;
  7. after generation, the only permitted source-tree status is the exact
     generated `code/cubrim-rs/Cargo.lock`;
  8. lock bytes match each other and the frozen lock hash;
  9. both builds use `taskset -c 0-15`, `--release`, `--locked`, a distinct
     target root, release debug, and all four thread limits set to `4`;
  10. both binaries match by bytes, SHA-256, size, and build ID, and match the
     frozen binary identities;
  11. rustc and Cargo versions match the frozen toolchain;
  12. immediately before the first clone, both exact G6 unit names still have
      `LoadState=not-found`; no service, `perf.data`, map, cell, timing, or
      campaign output is made;
  13. receipt publication is no-clobber through a private unpredictable staging
      path and produces one mode-`0444` `receipt.env`;
  14. after removing all write bits, the exact canonical tree-manifest
      algorithm runs for both source and target trees; the receipt contains the
      closed `g6-prebuild-receipt-v1` key set from the preregistration and no
      other key;
  15. successful source and target trees are recursively read-only before
      their manifest identities are computed and before receipt publication;
  16. any signal, nonzero command, incomplete target, or receipt mismatch
      exits nonzero and never publishes a final receipt.

- [ ] Implement the helper with frozen constants and literal paths. It clones
  twice from the authenticated local canonical repository, checks out the exact
  commit, generates each lock, builds into the two literal targets, validates
  every identity, rechecks both unit names immediately before cloning, seals
  the trees, computes their final manifests, and publishes the receipt once.
- [ ] Add behavior-driven mutants: remove each `cmp`; change source commit,
  lock hash, binary hash, build ID, pin, a thread limit, `--locked`, release
  debug, or receipt mode; drop/rename/duplicate the empty root row; accept a
  root/nested symlink, FIFO, socket, unsafe path, or collision; permit a second
  clone to alias the first object store;
  inject `perf.data`; omit one receipt key; and publish a partial receipt.
  Every mutant must be killed by a named behavior assertion.
- [ ] Run `bash -n`, `shellcheck`, the positive/negative contract, and all
  mutants. Then rerun in a fresh process with the production body replaced by
  an immediate failure; the positive contract must become RED.

## Task 3: Implement validation, admission/campaign runner, and mapper

- [ ] TDD `current-profile-g6-validate.sh` and its contract. It is a separate
  one-shot pre-service helper: it rejects every validation path collision and
  both G6 units, clones a fresh detached validation source at the frozen
  commit, installs the exact sealed generated lock, builds only into the
  literal validation target, runs `cargo test --release --locked` and
  `cargo test --release --locked --test scheme_roundtrip -- --nocapture` with the exact
  pin/release-debug/thread environment, authenticates the sealed prebuild
  binary again, copies the generated lock and logs into the validation output,
  restores every suite side effect, removes the generated lock from the
  validation checkout, and proves that checkout clean. It removes all write
  bits from the validation source/target/output, computes their three canonical
  manifests, then publishes the closed `g6-validation-manifest-v1` file outside
  those covered roots at
  `/root/cubr-new24-full-binary-g6-validation-manifest-20260811/manifest.env`
  through the exact `.partial` sibling. It creates no service or
  performance/map/campaign artifact; the external manifest never authenticates
  itself.
- [ ] The validation contract uses command mocks and behavior-driven mutations
  for source/lock/toolchain drift, missing `--locked`, target/output collision,
  side-effect leakage, wrong suite command, binary substitution, performance
  creation, final-manifest tampering, and a second invocation. A failing or
  ambiguous production validation is terminal `NO-ATTEMPT`; it is never rerun
  under G6.

- [ ] Use the four authenticated G5 source-code blobs as a starting point while
  implementing every self-contained G6 contract in the preregistration and
  this plan. Replace runtime namespaces with the literal G6 paths. The runner
  accepts exactly `--admission-feasibility` or `--campaign`; it never accepts a
  build or validation mode.
- [ ] In admission mode, independently rederive the mode-`0444` receipt's
  closed schema, byte count/hash, source/target manifests, exact binary bytes,
  ELF metadata, and zero-performance counts, then compare them with the
  no-clobber admission-input file. Admission seals the receipt hash/bytes; it
  also authenticates the exact validation manifest. It does not require the
  later protected launch identity set. In campaign mode,
  require that later set and compare its receipt/admission identities with the
  same rederived values. The runner contains no Cargo invocation and fails if
  either immutable source/target tree is writable.
- [ ] Admission uses only the admission output variants and the admission
  service identity. It runs release/roundtrip result authentication, the
  pure-mock empty-environment cgroup test, the live-unit noninterference test,
  capability probing against `/usr/bin/true`, fixed address-join smoke, static
  map construction, and admission identity sealing. It must not decode a
  campaign cell or retain/interpret a performance/timing/family result.
- [ ] Campaign uses only the campaign output variants and campaign service
  identity. It reuses the admission map byte-for-byte, executes the three
  preregistered cells, and retains every correctness, counter, perturbation,
  mapping, conservation, attribution-power, repeatability, deadline, and
  publication gate from the reviewed G5 instrument.
- [ ] The cgroup self-test launches with the explicit allowlist only:
  `HOME`, `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `LC_ALL=C`,
  `PATH=/usr/bin:/bin`, and the four thread variables. Its fd-bound export is
  tied to the transient unit InvocationID/cgroup, cleans up exactly, and rereads
  the currently admitted unit after every test.
- [ ] Mapper schemas all start `cubr-new24-g6-`. Runtime joining uses MMAP2 and
  DSO offset, is symbol-independent, conserves every sample and period, and
  voids any exact-binary unresolved or ambiguous inline owner.
- [ ] Implement the closed launch-identity parser in the runner and runner
  tests now. It rejects missing, duplicate, unknown, unsorted, malformed,
  mutable, self-referential, or G5-runtime values. Task 7 may populate a
  concrete file but may not change parser or instrument bytes.
- [ ] Carry forward the complete G5 mutation suite and add G6-specific mutants
  for receipt bypass, source/target writability, wrong admission-vs-campaign
  identity, map regeneration during campaign, Cargo invocation, sample
  creation during admission, and every G5 runtime literal. Run Python unit
  tests, shell syntax/lint, pure-mock tests, live-unit tests where feasible,
  and fresh-process mutation proof.

## Task 4: Review and land the eight-file instrument

- [ ] Record all eight Git blobs and prove the G5 instrument paths have their
  baseline blobs.
- [ ] Obtain a fresh independent specification review for the exact eight-file
  diff, fix every finding, and rerun it. Then obtain a separate fresh quality
  review and fix/review until both say ready for the same blobs.
- [ ] Normally add the eight owned instrument files, commit, push, and open a
  PR containing exactly those eight paths.
- [ ] Require terminal-success CI on the exact final head, merge normally,
  fetch the resulting `origin/main`, and prove head ancestry plus all eight blob
  identities. That resulting main is `CUBR_NEW24_G6_INSTRUMENT_MAIN`.

## Task 5: Materialize exact main and execute the prebuild once

- [ ] On `dev-ai`, authenticate the canonical source repository against fresh
  GitHub `origin/main`, prove the frozen source commit exists, and prove all G6
  source/target/receipt/admission-input/unit/output paths and variants are
  absent and not symlinks.
- [ ] Materialize `/root/cubr-new24-full-binary-g6-instrument` from exact
  `CUBR_NEW24_G6_INSTRUMENT_MAIN`. Compare every instrument blob and mode with
  resulting main; run all non-destructive test suites from that checkout.
- [ ] Execute the helper exactly once with this outer environment; the helper
  itself sets and checks the build pin/thread variables:

  ```bash
  /usr/bin/env -i HOME=/root CARGO_HOME=/root/.cargo \
    RUSTUP_HOME=/root/.rustup LC_ALL=C \
    PATH=/root/.cargo/bin:/usr/bin:/bin \
    /root/cubr-new24-full-binary-g6-instrument/documentation/ephemeral/research/current-profile-g6-prebuild.sh
  ```

  Record its exit status and complete output. The first invocation consumes
  the G6 prebuild allowance; never invoke it a second time under G6.
- [ ] If it fails, preserve every owned path read-only, record terminal
  `NO-ATTEMPT / NO-SELECT`, skip Tasks 6–8, and proceed to Task 9.
- [ ] If it succeeds, independently rederive the receipt stream, tree modes,
  source states, lock hashes/blobs, binary hashes/sizes/build IDs, toolchain,
  command environment, and exhaustive zero-performance/zero-service counts.
  Any disagreement is terminal `NO-ATTEMPT`; it does not authorize another
  prebuild.

## Task 6: Execute one no-performance admission

- [ ] Before creating a service, prove the three validation paths plus both
  validation-manifest roots are absent, then invoke the landed validation
  helper exactly once:

  ```bash
  /usr/bin/env -i HOME=/root CARGO_HOME=/root/.cargo \
    RUSTUP_HOME=/root/.rustup LC_ALL=C \
    PATH=/root/.cargo/bin:/usr/bin:/bin CARGO_PROFILE_RELEASE_DEBUG=1 \
    CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    /root/cubr-new24-full-binary-g6-instrument/documentation/ephemeral/research/current-profile-g6-validate.sh
  ```

  The first invocation consumes the validation allowance. Preserve its exact
  output/status and independently rederive all three covered-tree manifests
  and the closed external validation-manifest stream. A
  failure, frozen-source defect, or scientific-suite defect terminates G6
  `NO-ATTEMPT`; no source/scientific variable changes and validation is never
  rerun. The sealed prebuild source/targets remain unmodified.
- [ ] Prove the admission unit and every admission output variant are absent,
  the campaign unit/output variants are absent, the host/load/process gates
  pass, and the receipt remains exact.
- [ ] Derive and publish the mode-`0444`, no-clobber canonical
  `/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env` from the exact
  current instrument main and independently rederived receipt. Require the
  closed preregistered schema and verify every value again in a separate
  process before service submission.
- [ ] Create exactly one transient unit:

  ```bash
  /usr/bin/systemd-run --unit=cubr-new24-full-binary-g6-admission-20260811.service \
    --property=Type=exec --property=Restart=no --property=RuntimeMaxSec=4h \
    --property=KillMode=control-group --property=KillSignal=SIGTERM \
    --property=FinalKillSignal=SIGKILL \
    /usr/bin/env -i HOME=/root XDG_RUNTIME_DIR=/run/user/0 \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus LC_ALL=C \
    PATH=/usr/bin:/bin CUBR_THREADS=4 RAYON_NUM_THREADS=4 \
    OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    CUBR_G6_ADMITTED_UNIT=cubr-new24-full-binary-g6-admission-20260811.service \
    CUBR_G6_ADMISSION_INPUTS=/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env \
    /usr/bin/taskset -c 0-15 \
    /root/cubr-new24-full-binary-g6-instrument/documentation/ephemeral/research/current-profile-g6-run.sh \
    --admission-feasibility
  ```

  The first `systemd-run` submission consumes the admission allowance even if
  the client returns nonzero, disconnects, or cannot recover a unit identity.

- [ ] Bind monitoring and journal capture to that one InvocationID. Verify
  `Restart=no`, `NRestarts=0`, exact MainPID/cgroup, terminal state, absence of
  descendants, and the runner's final marker.
- [ ] On failure or ambiguity, preserve the admission tree and journal
  read-only as terminal `VOID / NO-SELECT`; do not create a second admission
  and proceed to Task 9.
- [ ] On success, verify the no-clobber final admission tree, authenticate its
  manifest, and prove exhaustive counts of campaign cells, `perf.data`, stat,
  record, attribution, timing, and interpreted-family artifacts are zero.
  Independently derive the static-map seal and canonical admission identity
  set SHA-256/bytes.

## Task 7: Land the concrete campaign identity set

- [ ] Add
  `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-LAUNCH-IDENTITIES-20260811.env`
  as the only changed path, with concrete values derived from Tasks 4–6. Keep
  the preregistration byte-identical to `CUBR_NEW24_G6_BASELINE`; its original
  blob is the schema's `g6_prereg_blob`. The
  canonical sorted schema includes instrument/resulting-main blobs; the exact
  12-field G5 incident and controlling-preregistration provenance set defined
  above; source/tree/subtree/Cargo inputs; lock; both targets and binaries;
  toolchain/env/flags; receipt; all eight instrument blobs; corpus rows;
  validation helper/test and manifest; map streams and parts; admission
  input/unit/InvocationID/manifest; and the admission identity set.
- [ ] Run the already-landed parser and mutation tests against the proposed
  file. Do not modify any of the eight instrument files after admission. Record
  exact proposed blobs and obtain independent specification then quality
  approval for those bytes. The file never claims its own blob.
- [ ] Force-add exactly the ignored launch `.env` path, then land that one-file
  change through a normal protected PR with terminal-success exact-head CI:

  ```bash
  git add -f -- documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-LAUNCH-IDENTITIES-20260811.env
  test "$(git diff --cached --name-only)" = documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-LAUNCH-IDENTITIES-20260811.env
  ```

  Fetch resulting main and prove blob parity. Independently record the reviewed
  PR head, identity-file blob from resulting main, and resulting-main commit;
  these three live values form the self-reference-free launch provenance.

## Task 8: Revalidate fresh main and launch one campaign

- [ ] Fetch `origin/main` immediately before launch and require equality with
  GitHub's live main. Reauthenticate every protected identity, remote file,
  mode, receipt, admission seal, code/corpus identity, suite result, load and
  process gate from scratch.
- [ ] Rematerialize the instrument checkout at the launch-file resulting
  main. Prove all eight instrument blobs are byte-identical to the admission
  instrument and that the only new consumed input is the protected launch
  identity file.
- [ ] Prove the campaign service and every campaign output variant are absent.
  A stale main, mismatch, collision, symlink, competing process, or gate miss
  is `NO-LAUNCH`; do not create the service.
- [ ] Create exactly one campaign unit:

  ```bash
  /usr/bin/systemd-run --unit=cubr-new24-full-binary-g6-20260811.service \
    --property=Type=exec --property=Restart=no --property=RuntimeMaxSec=4h \
    --property=KillMode=control-group --property=KillSignal=SIGTERM \
    --property=FinalKillSignal=SIGKILL \
    /usr/bin/env -i HOME=/root XDG_RUNTIME_DIR=/run/user/0 \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus LC_ALL=C \
    PATH=/usr/bin:/bin CUBR_THREADS=4 RAYON_NUM_THREADS=4 \
    OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    CUBR_G6_ADMITTED_UNIT=cubr-new24-full-binary-g6-20260811.service \
    CUBR_G6_LAUNCH_IDENTITIES=/root/cubr-new24-full-binary-g6-instrument/documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-LAUNCH-IDENTITIES-20260811.env \
    /usr/bin/taskset -c 0-15 \
    /root/cubr-new24-full-binary-g6-instrument/documentation/ephemeral/research/current-profile-g6-run.sh \
    --campaign
  ```

  Record the new InvocationID, MainPID, cgroup, and monotonic start. The first
  submission consumes the campaign allowance even on a nonzero/ambiguous
  client result; never create a second G6 campaign service.
- [ ] Monitor only that invocation to terminal state. Preserve timeout,
  nonzero exit, identity drift, late-final, manifest mismatch, or surviving
  descendant as `VOID / NO-SELECT`; never restart, resume, shorten, widen,
  substitute, or regenerate the map.

## Task 9: Package and land the terminal route

**Owned result paths:**

- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811.md`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811/identities.tsv`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811/unit-properties.txt`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811/systemd-journal.canonical.jsonl`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811/remote-tree-manifest.tsv`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811/remote-evidence/`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811/result.json`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811/verify_result.py`
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-RESULTS-20260811/test_verify_result.py`

- [ ] Capture invocation-bound unit properties and JSON journal; generate an
  exact path/type/mode/owner/size/hash manifest and byte-exact copy of every
  owned remote tree. Include prebuild-only, admission-terminal, or
  campaign-terminal evidence according to the route actually reached.
  Canonicalize journal events by `__CURSOR` and sorted JSON keys. If a service
  was not submitted, its fixed evidence file contains an explicit
  `[NOT REACHED: reason]` record; absence is never converted to `N/A` or PASS.
- [ ] Produce a deterministic `result.json` and narrative with one of:
  `NO-ATTEMPT / NO-SELECT`, `VOID / NO-SELECT`,
  `VALID-DESCRIPTIVE / NO-SELECT`, or
  `VALID-ATTRIBUTION / NO-SELECT`. Evaluate P1–P5 separately for each file;
  never aggregate files or select a source change.
- [ ] Implement a fail-closed whole-package verifier and mutation tests for
  every identity, terminal-state, zero-sample/admission, mapping,
  conservation, statistical, publication, and no-selection predicate. Run the
  verifier in a fresh process, delete or alter one result-bearing input in a
  temporary copy to prove RED, restore it, and prove fresh-process GREEN.
- [ ] Obtain independent specification and quality approval for the exact
  result package, land it through a normal PR with terminal-success exact-head
  CI, and verify resulting-main blob/tree parity.
- [ ] Re-read `origin/main` and the NEW-24 database row read-only. Confirm this
  experiment made no database/API/site/social/credential mutation, left
  measurement fields empty and evaluation zero, and created no duplicate row.
  Any later evidence-pointer transaction is a separate reviewed task.

## Completion gate

This plan is complete only when one terminal route is immutable on exact
`origin/main`, every one-shot transition actually reached has unique terminal
provenance, all exact-package tests and mutations pass, the G5 evidence is
unchanged, and the external-effect boundary is reverified. A green local test,
open PR, successful admission, or terminal service alone is not completion.
