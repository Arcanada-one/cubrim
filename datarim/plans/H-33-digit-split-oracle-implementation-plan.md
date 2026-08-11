# H-33 digit/non-digit split oracle implementation plan

**Goal:** implement, review, and land the prospective H-33 oracle instrument
without reading an H-33 outcome; only after exact-resulting-main and
pre-performance admission may one immutable 24-file campaign be launched.

**Architecture:** one pure Python oracle/validator owns framing, exact command
construction, the closed 24-file/384-step state machine, publication, and
result classification. A separate pure Python launcher owns the stopped-child
user-systemd containment seam. Tests use synthetic bytes, a fake Cubrim child,
and a fake systemd controller; real-corpus paths are never opened by tests or
pre-merge verification. The committed license fixture is deterministic and
read-only at execution. The landed preregistration is the sole semantic
authority.

**Landed authority:**

- plan-review base (fresh `origin/main`):
  `099c9406460b72e5fb201f04ab11a63ef6b70d6e`;
- preregistration:
  `documentation/ephemeral/research/CUBR-H33-DIGIT-SPLIT-PREREG-20260810.md`;
- preregistration SHA-256:
  `65a3dcdd5d7d48d8b8db480dc2eb18bfab3b6f4b2cd3c7a1268df26519e7307a`;
- inventory serialization SHA-256:
  `33dda3acf23f1a7dff903114481fa9ecd0da60270c25df2976568c8622224695`;
- license-fixture SHA-256:
  `b728c6903a00faa4e9d69eaf8aa2f743b8dd3363da1776998bce75948e5ac060`.

Historical registry `status=go` is triage provenance, not a result. This plan
does not authorize database, API, site, social, credential, or backlog writes.
It authorizes no performance estimate, partial-universe claim, retry, resume,
or candidate implementation.

## Task 1: Freeze the owned implementation surface and RED contracts

**Files:**

- Create:
  `documentation/ephemeral/research/h33_digit_split_oracle.py`
- Create:
  `documentation/ephemeral/research/test_h33_digit_split_oracle.py`
- Create:
  `documentation/ephemeral/research/h33_cgroup_launcher.py`
- Create:
  `documentation/ephemeral/research/test_h33_cgroup_launcher.py`
- Create:
  `documentation/ephemeral/research/h33-license-state.json`
- Modify: `.github/workflows/ci.yml`

1. Fresh-fetch and require the planning worktree to be a clean descendant of
   the current remote main. Before implementation, create a new implementation
   worktree/branch from a freshly authenticated `origin/main`; never implement
   in this plan worktree.

   ```bash
   git fetch origin main
   remote_main=$(git ls-remote origin refs/heads/main | awk '{print $1}')
   test "$remote_main" = "$(git rev-parse origin/main)"
   git merge-base --is-ancestor 367b6c74143ce9d6d987d9e75f47cd8f70813ce7 origin/main
   test "$(git show origin/main:documentation/ephemeral/research/CUBR-H33-DIGIT-SPLIT-PREREG-20260810.md | sha256sum | awk '{print $1}')" = 65a3dcdd5d7d48d8b8db480dc2eb18bfab3b6f4b2cd3c7a1268df26519e7307a
   ```

   **Expected:** all commands exit zero; no local ref is substituted for the
   remote readback.

2. Create an importable API scaffold whose public methods raise the exact
   sentinel `NotImplementedError("H33_NOT_IMPLEMENTED:<symbol>")`. Then use one
   minimal behavior cycle at a time: add one named test, run only that test and
   require its intended sentinel/assertion failure, implement the least code to
   pass, rerun that test, then run all previously green tests. A whole-suite
   missing-import failure is not RED evidence. Write
   `test_h33_digit_split_oracle.py` with `unittest.TestCase` classes and no
   optional discovery hook. Cover, at minimum:

   - exact 24-row inventory, order, byte counts, input hashes, canonical TSV,
     and inventory SHA;
   - exactly P01-P08, M001-M384, S01-S14 with each file owning one contiguous
     16-step block and eight timed operations;
   - strict ASCII digit-run split/rejoin, stable rejection
     `EMPTY_INPUT_UNSUPPORTED` for empty input, single-run/alternating runs,
     canonical minimal unsigned LEB128, overflow, truncation, zero run, wrong
     total, unknown selector/version, trailing bytes, and component mismatch;
   - exact fully charged branch sizes including selector/version/length fields,
     with ties selecting baseline;
   - fake-Cubrim whole-file fallback and three component calls in exact order;
   - exact `/usr/bin/env -i`, timeout, GNU-time, taskset, Cubrim, and harness
     arrays for B1/B2/O1/O2 encode/decode;
   - locale-C GNU-time parsing, checked nanoseconds, duplicate/missing fields,
     and charged max of GNU RSS vs cgroup memory peak;
   - return-code/type checks that reject booleans and noncanonical JSON types;
   - per-replicate exact namespace, create-new behavior, cleanup allowlist, and
     exhaustive payload-manifest membership;
   - independent result booleans, exact nci gate integers `1554693`, `1449272`,
     `105421`, exact rational `105421/1554693`, and VOID-first label precedence;
   - publication transitions STAGE -> PUBLISHING -> FINAL, fsync boundaries,
     quarantine after a post-final validation failure, and no overwrite/resume;
   - no database/API/network/social/credential call surface.

3. Apply the same named-test RED/sentinel/GREEN sequence to
   `test_h33_cgroup_launcher.py`. Tests exercise dependency injection, not PATH
   interception. Cover exact argument parsing, rejected
   extra args, OP names, unit names, stopped-before-exec handshake,
   `/proc/<pid>/cgroup` equality, UID/GID/capability checks, descendant census,
   AF_INET denied/AF_UNIX allowed preflight, memory/pids evidence, OOM counters,
   create-new stdout/stderr/evidence files, child reap, timeout escalation, and
   stable error codes. No test creates a real systemd unit.

4. Add mutation cases for every frozen integer/string/path and each terminal
   transition. Each mutation must prove one specific stable rejection code.
   Generate the registered-code set from the production enum and assert exact
   equality with the mutation-case set; no registered but untested error code
   and no mutation without a code is allowed.

5. Preserve a per-cycle RED/GREEN log containing the exact named test, intended
   failure, and subsequent pass. After all cycles, run both complete suites:

   ```bash
   python3 -m unittest -v \
     documentation.ephemeral.research.test_h33_digit_split_oracle \
     documentation.ephemeral.research.test_h33_cgroup_launcher
   ```

   **Expected:** zero. The durable cycle log proves each behavior's RED rather
   than one broad import failure. Commit no sentinel implementation.

## Task 2: Implement and authenticate the deterministic license fixture

1. Before the fixture exists, add and run only its raw-byte contract test and
   require `FileNotFoundError` for the exact fixture path. Then create
   `h33-license-state.json` with exactly these 150 UTF-8 bytes, including the
   final LF, rerun the named test GREEN, and append that RED/GREEN evidence to
   the cycle log:

   ```json
   {
     "install_id": "00000000-0000-4000-8000-000000000033",
     "accepted": true,
     "license_version": "1.0.0",
     "accepted_at": "2026-08-10T00:00:00Z"
   }
   ```

2. The test reads raw bytes and requires size `150`, SHA-256
   `b728c6903a00faa4e9d69eaf8aa2f743b8dd3363da1776998bce75948e5ac060`,
   exact closed keys/types, nonnil UUID, accepted true, and version `1.0.0`.
   Reject BOM, CRLF, reordered/extra keys, missing final LF, or timestamp drift.

3. Add `license-state-prepare` and `license-state-check` subcommands to the
   oracle module. Prepare accepts only an exact committed fixture, refuses an
   existing nonidentical target, uses a private temporary sibling plus fsync
   and no-replace rename, then requires directory UID/GID `1002:1002` mode
   `0555` and file UID/GID `1002:1002` mode `0444`, regular/non-symlink/link
   count one. Check opens with `O_RDONLY|O_NOFOLLOW`, records inode/device/
   mode/owner/size/mtime-ns/hash, and can compare before/after identities.

4. Tests operate only in `tempfile.TemporaryDirectory`; mock numeric ownership
   without requiring root. Mutations cover symlink, hard link, wrong mode,
   writable file, replacement, changed inode, and changed bytes.

   **Expected:** focused license tests pass; repository paths and operator state
   remain untouched.

## Task 3: Implement the fail-closed cgroup launcher

1. `h33_cgroup_launcher.py` must be stdlib-only and expose exactly:

   ```text
   h33_cgroup_launcher.py run --unit UNIT --stdout PATH --stderr PATH \
     --evidence PATH -- COMMAND...
   h33_cgroup_launcher.py preflight --unit UNIT --stdout PATH --stderr PATH \
     --evidence PATH -- /usr/bin/true
   ```

   `python3 -I -B` is the only interpreter route. Reject relative paths,
   unknown options, missing `--`, empty command, unapproved OP/unit grammar,
   non-UID/GID 1002, any capability bit, and any preexisting destination.

2. Open stdout/stderr/evidence once with
   `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`, mode `0600`. Flush/fsync stdout and
   stderr, then write the final canonical JSON directly and exactly once through
   the already-open evidence FD, fsync it, close it, and fsync the directory.
   There is no temporary evidence path or rename onto the precreated final.

3. Fork the command child, have it enter a stopped handshake before `execve`,
   and make the parent authenticate `/proc` status, UID/GID/capability sets,
   exact service cgroup, inherited affinity `0-15`, and command/environment.
   Only then send `SIGCONT`. Use `pidfd_open` when available and otherwise
   exact PID/start-time binding; never identify descendants by process name.

4. Reap the process tree. At terminal, require only the launcher in
   `cgroup.procs`; record memory.peak, exact memory.events, pids.current,
   cgroup path, command status/signal, child/descendant identities, and timing.
   Any orphan, OOM/max event, escaped descendant, or unparseable file fails.

5. `preflight` additionally attempts an AF_INET socket and requires the exact
   permission-denied class, creates/closes an AF_UNIX socket successfully, then
   runs only `/usr/bin/true`. It never accepts an input/result/cell operand.

6. Make every launcher test GREEN. Run:

   ```bash
   python3 -m unittest -v documentation.ephemeral.research.test_h33_cgroup_launcher
   python3 -m compileall -q \
     documentation/ephemeral/research/h33_cgroup_launcher.py \
     documentation/ephemeral/research/test_h33_cgroup_launcher.py
   ```

   **Expected:** all tests pass, no user unit is created, and no H-33 namespace
   is opened.

## Task 4: Implement the pure transform, frame, and fake-child seam

1. Use immutable dataclasses/typed mappings for inventory rows, run segments,
   frame metadata, command records, cgroup records, observation rows, and the
   final label inputs. JSON readers require exact closed key sets, exact types,
   bounded integers, canonical lowercase SHA-256, and reject `bool` as `int`.

2. Implement streaming maximal ASCII digit/non-digit split with no outcome
   shortcut. Encode canonical minimal unsigned LEB128 and reject nonminimal,
   zero, overflowed, truncated, or trailing encodings. Reconstruction consumes
   all streams and proves exact original length.

3. Implement outer selector `0x00` fallback and selector/version `0x01/0x01`
   split frame exactly as preregistered. The encoded object contains every
   charged byte. Tie chooses fallback. Decode rejects before acceptance on any
   malformed field/component or unconsumed byte.

4. Isolate Cubrim execution behind an injected `run_child(argv, env, ...)`
   seam. Production permits only the authenticated absolute Cubrim path and
   exact arrays. Tests use a deterministic fake archive format and never invoke
   current Cubrim or corpus files.

5. Oracle encode creates fallback first, then three plain streams, then three
   component archives in run-map/digit/non-digit order, frames, validates,
   selects, fsyncs, and closes. Oracle decode parses selector and performs one
   or three exact child calls before reconstruction and fsync.

6. Make transform/frame/child-order tests GREEN. Add seeded property cases but
   store every seed explicitly; no time/random/environment-derived seed.

## Task 5: Implement the closed state machine and publication validator

1. Embed the exact 24 inventory tuples from the preregistration and generate
   the canonical TSV plus P/M/S manifest deterministically. A pre-outcome
   command `print-expected-manifest` may emit identities/paths/commands only;
   it must not stat/open `INPUT_ROOT`, create archives, or compute digit share.

2. Model one journal append per state transition with monotonically increasing
   ordinal, previous-record hash, current-record hash, run ID, operation, and
   stable status. Journal creation is exclusive. On any failure, append the
   primary error before bounded cleanup; cleanup cannot replace it.

3. Build B1/B2/O1/O2 command arrays literally from the preregistration.
   Environment is a closed ordered mapping including the read-only license
   state and cell TMPDIR. Persist NUL-safe argv and exact env before launch and
   byte-compare them in the validator.

4. For every replicate enforce exact create-new files:
   archive, encode/decode time, command JSON, cgroup JSON, unit stdout/stderr,
   verify JSON, decoded file, and tmp tree. The OP-specific launcher paths must
   match the preregistration. Cleanup removes only decoded/tmp after durable
   verification.

5. Implement strict GNU-time parsing, `cmp`/SHA roundtrip, deterministic pair
   equality, exact file gates, category gates, nci threshold, speed/RSS gates,
   and independent booleans. Terminal classification evaluates VOID first,
   then the fixed non-VOID precedence; it cannot select a candidate or write a
   registry disposition.

6. Implement S01-S14 publication with exhaustive manifest, bottom-up fsync,
   two no-replace renames, read-only modes, fresh-process readback, and
   quarantine on post-final failure. A visible partial tree is never COMPLETE.

7. Implement a `validate-tree --root PATH --execution-main SHA` command that
   rederives run/inventory/harness IDs, schemas, hashes, counts, order, labels,
   modes, namespace exclusivity, and exact-main object/blob provenance. It must
   not depend on moving source paths or current tool output after publication.

## Task 6: Prove pre-performance behavior with TDD and mutations

1. Add synthetic end-to-end fixtures for one miniature inventory and a
   generated full 24/384 manifest without real execution. Production constants
   remain immutable; the miniature fixture enters only through an injected
   test policy object that production CLI cannot select.

2. Mutate every authority dimension independently: execution commit/blob,
   inventory row/order/hash, license state, systemd unit/property/result,
   argv/env, cgroup evidence, timeout, branch/frame byte, archive hash/size,
   time/RSS, roundtrip, pair equality, step order/count, cleanup, manifest,
   status marker, final label, and read-only mode.

3. Add a test that monkeypatches all filesystem opens and fails if an
   implementation test attempts `/home/dev/cubrim-corpora/world-v1`,
   `/home/dev/cubrim-results/H-33-v1`, a registry connection, or a network
   socket outside the explicit AF-family preflight fake.

4. Add a test that the license/no-input feasibility command reaches the exact
   nonexistent-input open error twice (stock label and oracle-child label),
   while state identity/hash remain unchanged and no network call occurs. Use
   a fake child for unit tests; the real-binary probe is a later launch gate.

5. Run focused suites twice from fresh Python processes and compare their
   ordered test lists/output summaries. Require no repository diff.

## Task 7: Run repository verification and two independent reviews

1. Modify `.github/workflows/ci.yml` as the sixth owned file. Add
   `'documentation/ephemeral/research/h33*'` to both `push.paths` and
   `pull_request.paths`. Add exactly this Python 3.12 job, using the workflow's
   existing checkout/setup action versions and repository-root working
   directory:

   ```yaml
   h33-oracle-contract:
     name: H-33 oracle contracts
     runs-on: ubuntu-latest
     timeout-minutes: 10
     steps:
       - name: Check out source
         uses: actions/checkout@v4
       - name: Install Python
         uses: actions/setup-python@v5
         with:
           python-version: '3.12'
       - name: Run H-33 contract suites
         run: >-
           python -m unittest -v
           documentation.ephemeral.research.test_h33_digit_split_oracle
           documentation.ephemeral.research.test_h33_cgroup_launcher
   ```

   Add a structural test that parses the workflow text and requires both path
   triggers, Python 3.12, both exact module names, and no outcome/campaign CLI.

2. Run the exact local gate:

   ```bash
   python3 -m unittest -v \
     documentation.ephemeral.research.test_h33_digit_split_oracle \
     documentation.ephemeral.research.test_h33_cgroup_launcher
   python3 -m compileall -q \
     documentation/ephemeral/research/h33_digit_split_oracle.py \
     documentation/ephemeral/research/test_h33_digit_split_oracle.py \
     documentation/ephemeral/research/h33_cgroup_launcher.py \
     documentation/ephemeral/research/test_h33_cgroup_launcher.py
   cargo fmt --check --manifest-path code/cubrim-rs/Cargo.toml
   cargo test --release --manifest-path code/cubrim-rs/Cargo.toml
   git add -N -- \
     documentation/ephemeral/research/h33_digit_split_oracle.py \
     documentation/ephemeral/research/test_h33_digit_split_oracle.py \
     documentation/ephemeral/research/h33_cgroup_launcher.py \
     documentation/ephemeral/research/test_h33_cgroup_launcher.py \
     documentation/ephemeral/research/h33-license-state.json
   git diff --check
   ```

   **Expected:** every command exits zero. The two known test-generated files
   are exactly
   `documentation/ephemeral/research/CUBR-0028-bench.json` and
   `documentation/ephemeral/research/CUBR-0031-bench.json`. Record their HEAD
   blob hashes before testing; restore only these explicit paths, and only after
   proving the successful suite produced their diffs and no foreign edit
   overlaps them. Preserve all other changes. Intent-to-add is verification
   state only and is replaced by exact staging in Task 8.

3. Secret/scope scan only the six owned files. Reject credential values,
   tokens, private keys, URLs with userinfo, database DSNs, and any executable
   DB/API/site/social command. Literal policy terms in tests are not secrets;
   classify matches semantically instead of using a self-hitting blanket grep.

4. Give the exact commit to one independent spec reviewer and one independent
   executable-quality reviewer. Both are read-only and must return Ready YES.
   Resolve all Critical/Important findings with new RED/GREEN evidence and
   re-review the exact amended SHA.

## Task 8: Land the instrument through a protected PR

1. Stage exactly the six owned files (the four Python files, JSON fixture, and
   `.github/workflows/ci.yml`). Prove the reviewed path set equals the
   staged set and record each blob/SHA-256/byte count.

2. Push a normal feature branch, verify local HEAD equals upstream and
   `ls-remote`, create a PR with full test commands/results, and require a
   distinct human/code-owner approval if branch protection requests one. Never
   self-approve or bypass protection.

3. Wait for every required check to reach terminal success on the exact head.
   Rebase only if necessary; after any changed head, rerun all tests and both
   reviews before merge.

4. Merge normally. Fresh-fetch and require local remote-tracking main equals
   `ls-remote` main and the PR resulting merge commit. In a clean detached
   worktree at exact resulting main, compare every landed blob/hash with the
   reviewed set and rerun both focused Python suites plus the full release
   suite. Only this exact resulting main can become execution main.

## Task 9: Perform admission without H-33 outcome access

0. **Build-readiness precondition — run before anything in this task, and treat
   a NO-GO as terminal for the attempt rather than for the allowance.** On
   `arcana-devs`, in a scratch detached worktree at the intended resulting main
   and with a scratch target directory, run

   ```bash
   documentation/ephemeral/research/preflight-build-readiness.sh --repo <scratch>
   ```

   and require `BUILD_READINESS=GO`. It asserts `Cargo.lock` is *tracked* (not
   merely present in a working tree), that the toolchain resolves, that the lock
   and manifest agree, and that the frozen `--offline --locked` build actually
   succeeds against this host's cargo cache.

   This carries no scientific allowance and may be rerun without limit. It
   exists because the one-shot property belongs to the measurement, never to the
   environment check: an earlier revision of this plan would have reached step 1
   and failed the frozen build with `exit 101`, because `Cargo.lock` was
   gitignored and `--locked` refuses to create one, consuming the admission on a
   defect unrelated to H-33. Measured both sides in
   `documentation/ephemeral/research/CUBR-H33-BUILD-FEASIBILITY-20260811.md`.

   If the probe reports a download in offline mode, run `cargo fetch --locked`
   out of band, online, and re-run the probe. Crate availability is a property
   of this host's cargo home, not of the commit, so no merge can carry it.

   The probe changes no frozen scientific variable and does not alter the
   permitted build below; it runs the same array in a scratch location to prove
   it can pass.

1. On `arcana-devs`, create the exact detached execution worktree
   `/home/dev/.worktrees/cubrim/CUBR-H33-EXEC` at freshly authenticated
   resulting main. Refuse an existing nonmatching path. The exact build array is
   frozen before implementation review and is the only permitted build:

   ```text
   /usr/bin/env -i HOME=/home/dev PATH=/home/dev/.cargo/bin:/usr/bin:/bin \
     LANG=C LC_ALL=C TZ=UTC CARGO_HOME=/home/dev/.cargo \
     RUSTUP_HOME=/home/dev/.rustup CARGO_NET_OFFLINE=true \
     CARGO_TARGET_DIR=REPO/code/cubrim-rs/target-h33 \
     /home/dev/.cargo/bin/cargo build --offline --locked --release \
     --manifest-path REPO/code/cubrim-rs/Cargo.toml
   ```

   `REPO` is the one exact detached path, expanded before `execve`; there is no
   shell evaluation. Admission requires `/home/dev/.cargo/bin/cargo` and
   `rustc` to resolve to `/home/dev/.cargo/bin/rustup`, SHA-256
   `4acc9acc76d5079515b46346a485974457b5a79893cfb01112423c89aeb5aa10`,
   with exact version lines `cargo 1.97.1 (c980f4866 2026-06-30)` and
   `rustc 1.97.1 (8bab26f4f 2026-07-14)`. Authenticate the resulting binary,
   Cargo inputs, flags, prereg, harness, launcher, tests, fixture, and commit
   object. Any tool/cache miss or drift is `NO-LAUNCH`; never add a flag or
   fetch a dependency after review.

2. Create `/home/dev/cubrim-results/H-33-v1` only if its identity/ownership is
   exact and no run namespace/VOID journal exists. Provision the license state
   using only the landed fixture and `license-state-prepare`, then make it
   immutable by ownership/modes and retain the open read-only identity.

3. Run the real-binary license probe twice against a fixed deliberately
   nonexistent operand, once as stock-child and once as oracle-child. Require
   the exact post-license input-open error, unchanged license identity/hash,
   no state write, and no network. This is feasibility, not an outcome.

4. There is no rehearsal or `admission --no-outcomes` command that executes
   canonical P01-P04. In particular, no prelaunch command creates `STAGE`,
   `STAGE/preflight`, a campaign unit, or a campaign journal. The user-systemd
   disposable preflight occurs exactly once as canonical P04 inside the
   uninterrupted campaign; its failure is terminal `VOID`.

5. Immediately before launch, a fresh read-only `preview-launch` process checks
   exact main/blobs, host/tools/user-bus/license identity, input-root and result-
   root directory identities, all run namespaces absent, and load values each
   <=0.50 once. It may stat paths and read already-public identity metadata but
   must not open any corpus file, compute an input hash/digit count, create a
   namespace/unit/journal, or call a compression command. Failure is
   `NO-LAUNCH` and does not consume the one shot. Preview state is not promoted
   or reused; canonical P01-P08 rederive every authority after launch.

## Task 10: Launch exactly once and monitor read-only

1. Construct the deterministic RUN_ID/RUN_KEY from reviewed identities without
   opening outcome paths. The exact runtime budget is `14,938,980` seconds:
   `14,923,860` preregistered step deadlines + `192 * 60` seconds of timeout
   kill grace + `3,600` seconds of top-level terminal handling. Launch exactly
   this top-level array once, with every token expanded to one reviewed absolute
   value and passed by `execve` rather than a shell:

   ```text
   /usr/bin/env -i HOME=/home/dev PATH=/usr/bin:/bin LANG=C LC_ALL=C TZ=UTC \
     XDG_RUNTIME_DIR=/run/user/1002 \
     DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1002/bus \
     /usr/bin/systemd-run --user --service-type=exec \
     --unit=cubr-h33-RUN_KEY.service --property=Slice=app.slice \
     --property=Restart=no --property=KillMode=control-group \
     --property=TimeoutStopSec=60s --property=RuntimeMaxSec=14938980 \
     --property=StandardOutput=journal --property=StandardError=journal -- \
     /usr/bin/env -i HOME=/nonexistent PATH=/usr/bin:/bin LANG=C LC_ALL=C \
     TZ=UTC XDG_RUNTIME_DIR=/run/user/1002 \
     DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1002/bus \
     PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 \
     CUBRIM_ACCEPT_LICENSE=1 \
     CUBRIM_STATE_DIR=/home/dev/.local/share/cubrim-h33-license-v1 \
     /usr/bin/python3 -I -B HARNESS campaign \
     --execution-main EXECUTION_MAIN --cubrim CUBRIM \
     --input-root /home/dev/cubrim-corpora/world-v1 \
     --result-root /home/dev/cubrim-results/H-33-v1
   ```

   `HARNESS`, `EXECUTION_MAIN`, and `CUBRIM` are the single exact-main absolute
   values authenticated in Task 9 and stored in P01. Reject any extra env,
   property, or argument. Record the invocation ID before reading results.

2. The campaign executes P01-P08, M001-M384, S01-S14 without branches,
   retries, resume, retuning, file omission, or concurrent cells. The only
   permitted data writes are the frozen license destination before launch,
   campaign namespaces, systemd runtime state, and a VOID journal on a started
   campaign failure.

3. Monitor read-only. Do not restart, repair, copy partial evidence, or inspect
   archive sizes/digit shares until the unit is terminal and the namespace is
   either exact FINAL with STATUS.COMPLETE or exact VOID evidence.

4. Authenticate Result, ExecMainStatus, NRestarts, invocation ID, no orphan,
   final/partial/quarantine exclusivity, manifest, modes, hashes, and fresh-
   process validator before result interpretation. Any ambiguity is VOID.

## Task 11: Package the terminal result without registry mutation

1. In a new exact-main result worktree, copy the immutable raw tree
   byte-for-byte, prove source/destination exhaustive manifests, and add a
   version-frozen validator plus mutation tests. Never rerun the campaign.

2. Report all 24 per-file rows and exact category/gate booleans. Do not compute
   a corpus-wide density or speed average, hide Canterbury, infer unmeasured
   performance, or convert a VOID/partial result to NO-GO.

3. Independently review raw-to-validator-to-report consistency. Land raw
   evidence, validator, tests, and report through a second protected exact-head
   PR; verify exact resulting-main blobs.

4. This task ends with an evidence result only. Any H-33 registry disposition,
   candidate construction, product change, or deployment requires a separately
   reviewed pointer/disposition plan and explicit authority.

## Definition of done

- The plan and preregistration land before implementation.
- The six-file instrument/CI change lands on protected main with full tests and two
  independent Ready reviews before any outcome access.
- Admission is demonstrably outcome-free and exact-host feasible.
- At most one campaign launch occurs; no restart or resume occurs.
- Every one of 24 files has exact roundtrip and per-file measurements, or the
  whole attempt is honestly VOID.
- Terminal evidence and its result package land on exact main.
- No database/API/site/social/credential/backlog mutation is implied or made.

## Path validation

At plan drafting, the landed preregistration, `.github/workflows/ci.yml`, and
repository/test commands exist. The four Python implementation files and JSON
fixture are explicitly to be created. `CUBR-H33-EXEC`, the corpus root, result root, license-state
destination, and transient user-systemd units are execution prerequisites and
must be proven by Task 9; their absence now is not represented as PASS.
