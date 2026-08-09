# NEW-24 Decode Attribution G2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` (recommended, when your runtime supports spawning isolated agents) or `executing-plans` (single-session execution) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land and execute one fail-closed, preregistered decode-attribution campaign on `dev-ai` that characterizes the four NEW-24 cells without proposing a Fast-CM lever or writing performance measurements to the database.

**Architecture:** Preserve the original preregistration and add a prospective amendment that classifies foreign Generation 0 as invalid. Harden the existing Bash runner into a unique Generation G2 instrument with executable contract tests, exact source/binary provenance, two-encode canonical gates, byte-exact round trips, bounded `perf` collection, and immutable checksummed evidence. Merge the reviewed instrument to `main` before copying and launching its exact bytes once under systemd.

**Tech Stack:** Bash 5, ShellCheck, GNU coreutils, Git worktrees, Cargo/Rust tests, Linux `perf`, systemd transient services, PostgreSQL read-only timing inputs.

---

### Task 1: Freeze the correction and write RED runner-contract tests

**Files:**
- Modify: `documentation/ephemeral/research/CUBR-DECODE-ATTRIB-AMENDMENT-20260809.md`
- Create: `documentation/ephemeral/research/decode-attrib-run-test.sh`
- Test: `documentation/ephemeral/research/decode-attrib-run-test.sh`

- [ ] **Step 1: Complete the amendment self-review**

Check that the amendment discloses the bounded G0 journal fields already read, records the actual EPYC topology (logical CPUs 0-31 are distinct physical cores; 32-63 are SMT siblings), freezes the four timeout pairs, preserves P1-P5 unchanged, and contains no claim that G0 was unread or that a directory is intrinsically tamper-proof.

Run:

```bash
rg -n 'No Generation 0 observation|16.?31 SMT|tamper-proof|TBD|TODO' \
  documentation/ephemeral/research/CUBR-DECODE-ATTRIB-AMENDMENT-20260809.md
```

Expected: no matches.

- [ ] **Step 2: Write the failing static contract test**

Create a Bash test that sets `RUNNER` to `decode-attrib-run.sh`, exits nonzero on a missing required literal, and asserts all of these contracts:

```text
/root/cubr-decode-attrib-g2-20260809
taskset -c 0-15
/root/corpus-full/silesia
d4b9fc85a242f887fb1a49bd849c35779c48b8fda04480969309f2d0bb0211cb
3a13f48
cargo test --release
cargo test --release --test differential -- --nocapture
cmp --
corpus_manifest.tsv
perf stat
perf record
SHA256SUMS
TIMING-DONE.STAMP
```

The same test must reject `taskset -c 16-19`, the G0 output path as an assignment, unbounded direct candidate invocations, and a runner that omits output-path refusal, campaign-deadline handling, cycle-agreement classification, or instrument-perturbed classification.

- [ ] **Step 3: Prove RED against the landed runner**

Run:

```bash
bash documentation/ephemeral/research/decode-attrib-run-test.sh
```

Expected: FAIL, identifying the first absent G2 contract; the old runner must not accidentally satisfy the new protocol.

- [ ] **Step 4: Commit the prospective protocol and RED test**

```bash
git add -f datarim/plans/NEW-24-decode-attrib-g2-plan.md
git add documentation/ephemeral/research/CUBR-DECODE-ATTRIB-AMENDMENT-20260809.md \
  documentation/ephemeral/research/decode-attrib-run-test.sh
git commit -m "research: amend NEW-24 attribution protocol"
```

### Task 2: Implement fail-closed G2 admission and provenance

**Files:**
- Modify: `documentation/ephemeral/research/decode-attrib-run.sh`
- Test: `documentation/ephemeral/research/decode-attrib-run-test.sh`

- [ ] **Step 1: Add immutable constants and strict execution mode**

Use `set -euo pipefail`, `LC_ALL=C`, absolute paths for security-sensitive commands, `OUT=/root/cubr-decode-attrib-g2-20260809`, an array `PIN=(/usr/bin/taskset -c 0-15)`, the full binary SHA, code commit `3a13f48`, the four exact archive/original hashes, and the frozen timeout table from the amendment. Refuse execution unless invoked as `--run`; add `--self-test` for pure contract tests.

- [ ] **Step 2: Refuse collisions before creating output**

Before `mkdir`, require that `$OUT` and `$OUT.partial` are absent. Create `$OUT.partial`, write all active evidence there, and rename it atomically to `$OUT` only after final manifests and `TIMING-DONE.STAMP` are complete. Never reference, remove, or write under `/root/cubr-decode-attrib-20260809`.

- [ ] **Step 3: Enforce host, topology, process, binary, code, and runner admission**

Fail before suites or measurement unless:

```text
hostname -s == dev-ai
logical CPU/core mapping is 0->0 through 31->31 and 32->0 through 63->31
no other cubrim-3a13f48, decode-attrib runner, perf stat, or perf record process exists
1-minute load average < 8.0
frozen binary SHA matches
detached code checkout HEAD is 3a13f48 and clean
reviewed runner SHA supplied by the external launch gate matches the live script
bounded perf stat and perf record smoke probes succeed
```

Exclude the current runner PID and its parent systemd shell from the competing-process test. Journal every admission value without credential or environment dumps.

- [ ] **Step 4: Run the RED contract test**

```bash
bash documentation/ephemeral/research/decode-attrib-run-test.sh
```

Expected: progress beyond the prior failure; any remaining gate fails with its exact missing contract.

- [ ] **Step 5: Commit admission hardening**

```bash
git add documentation/ephemeral/research/decode-attrib-run.sh \
  documentation/ephemeral/research/decode-attrib-run-test.sh
git commit -m "research: harden NEW-24 attribution admission"
```

### Task 3: Implement the suite, canonical, round-trip, timeout, and perf gates

**Files:**
- Modify: `documentation/ephemeral/research/decode-attrib-run.sh`
- Modify: `documentation/ephemeral/research/decode-attrib-run-test.sh`

- [ ] **Step 1: Run exact-code suites before any cell**

Run `/root/.cargo/bin/cargo test --release` and `/root/.cargo/bin/cargo test --release --test differential -- --nocapture` in the detached `3a13f48` checkout. The focused target is the round-trip/back-compat integration target that actually exists at the frozen commit; the later `scheme_roundtrip` target is not present and must not be overlaid. If the suites modify the two known tracked benchmark JSON files, verify that exact allowlist, restore their HEAD blobs atomically, and prove the checkout clean; any other side effect fails the campaign.

- [ ] **Step 2: Resolve and freeze every source through the manifest**

Use `/root/corpus-full/<corpus>/<file>`, parse exactly one matching `corpus_manifest.tsv` row, and require its corpus, file, byte count, and SHA to equal the runner constants before encoding. This must make `xml/max` resolvable and must reject zero or duplicate manifest rows.

- [ ] **Step 3: Implement G1 with two independent encodes**

For each cell, run two separately timed-out encodes to distinct files. Require both SHA-256 values to equal the historical Phase C journal hash and require `cmp -- first.cub second.cub` to succeed. Use the second archive for all decodes. Encode wall time is gate evidence only and is never reported as a speed result.

- [ ] **Step 4: Implement G2 for every decode**

Delete the prior output, execute the decode under the appropriate wrapper, require exit zero, `cmp --` output against the source, and require output SHA equal the pinned manifest SHA. A failure journals one cell failure and prevents all later observations for that cell.

- [ ] **Step 5: Enforce time and campaign budgets**

Use a monotonic start/deadline. Wrap every encode/decode with `/usr/bin/timeout --signal=TERM --kill-after=10s`, limiting it to the lesser of the frozen per-step timeout and remaining four-hour budget. Refuse to start after the deadline; journal active/unfinished cells as void and exit without substitution. The systemd `RuntimeMaxSec=4h5m` remains only a last-resort cap.

- [ ] **Step 6: Collect and classify perf evidence**

Run one plain `/usr/bin/time -v` decode, two `perf stat -d` decodes with tab-delimited explicit events, and one `perf record -F 997 -e cycles` decode. Parse exact numeric cycle counts, require both stat runs to expose every required event, calculate their symmetric/max-relative disagreement, and classify `cycle-agreement` only at `<=0.10`. Calculate record/plain wall ratio and classify `instrument-perturbed` above `1.10`; preserve symbol shares but forbid a cycles/bit claim for that cell.

- [ ] **Step 7: Finalize evidence atomically**

After every cell, reject orphan candidate/perf processes. At campaign end, write sorted manifests covering every raw file, journal, suite log, runner copy, binary hash, and code identity; write `TIMING-DONE.STAMP` last; rename `.partial` to the final path; then remove write permission recursively.

- [ ] **Step 8: Make the contract test GREEN**

```bash
bash -n documentation/ephemeral/research/decode-attrib-run.sh
shellcheck documentation/ephemeral/research/decode-attrib-run.sh \
  documentation/ephemeral/research/decode-attrib-run-test.sh
bash documentation/ephemeral/research/decode-attrib-run-test.sh
```

Expected: all commands exit 0 and the test prints `decode_attrib_contract=PASS`.

- [ ] **Step 9: Run source-bound mutation tests and commit**

Mutate, one at a time in temporary copies, the pin, output path, manifest SHA check, `cmp`, timeout, G3 threshold, cycle threshold, suite command, completion-marker ordering, and runner-provenance check. Each mutant must make the contract test fail. Then commit only the canonical files:

```bash
git add documentation/ephemeral/research/decode-attrib-run.sh \
  documentation/ephemeral/research/decode-attrib-run-test.sh
git commit -m "research: enforce NEW-24 attribution gates"
```

### Task 4: Review and land the instrument before measurement

**Files:**
- Review: `documentation/ephemeral/research/CUBR-DECODE-ATTRIB-AMENDMENT-20260809.md`
- Review: `documentation/ephemeral/research/decode-attrib-run.sh`
- Review: `documentation/ephemeral/research/decode-attrib-run-test.sh`
- Review: `datarim/plans/NEW-24-decode-attrib-g2-plan.md`

- [ ] **Step 1: Independent spec review**

Give the exact commit SHA to a read-only subagent. Require confirmation that every original cell/prediction/sample count is unchanged, all operator hard constraints are encoded, G0 is preserved/invalid, and no measurement or Fast-CM lever is claimed.

- [ ] **Step 2: Independent quality review**

Give the same exact SHA to a separate read-only subagent. Require adversarial review of shell safety, timeout semantics, process matching, manifest parsing, `perf` parsing, completion ordering, mutation coverage, and archive/round-trip gates. Critical or Important findings return to Tasks 1-3.

- [ ] **Step 3: Re-run final verification**

```bash
git diff --check origin/main...HEAD
bash -n documentation/ephemeral/research/decode-attrib-run.sh
shellcheck documentation/ephemeral/research/decode-attrib-run.sh \
  documentation/ephemeral/research/decode-attrib-run-test.sh
bash documentation/ephemeral/research/decode-attrib-run-test.sh
git status --short
```

Expected: all checks pass and the worktree is clean.

- [ ] **Step 4: Normal PR and exact-main merge**

Fetch and rebase on current `origin/main`, repeat exact-SHA reviews if the SHA changes, push normally, open a non-draft PR, wait for terminal-success checks for that exact head, and merge without admin bypass. Fetch current `origin/main` and verify every owned blob landed before any stand copy or profiling command.

### Task 5: Launch G2 once from exact main

**Files:**
- Execute from landed: `documentation/ephemeral/research/decode-attrib-run.sh`
- Preserve remote: `/root/cubr-decode-attrib-20260809`
- Create remote: `/root/cubr-decode-attrib-g2-code`
- Create remote: `/root/cubr-decode-attrib-g2-20260809.partial`
- Final remote: `/root/cubr-decode-attrib-g2-20260809`

- [ ] **Step 1: Wait for foreign G0 without touching it**

Read only its process status. Do not signal, delete, restart, copy from, or parse additional G0 results. Continue only after every G0 runner/candidate/perf process has exited.

- [ ] **Step 2: Create the exact detached code checkout**

From the existing `/root/cubr-levers` repository, create `/root/cubr-decode-attrib-g2-code` at exact commit `3a13f48`, verify `git rev-parse HEAD`, clean status, and candidate binary SHA. Refuse if that path already exists.

- [ ] **Step 3: Copy and authenticate exact-main runner bytes**

Fetch current main locally, verify the landed runner/test/amendment blobs, copy the runner once to a new remote path, and verify its SHA-256 after transfer. The external launch command must pin current main, the reviewed runner hash, the remote host, and absence of the G2 output paths.

- [ ] **Step 4: Run bounded preflight without measurement**

Execute `--self-test`, Bash syntax, stand topology, process, perf smoke, binary, code, corpus, journal, and output-path gates. Capture the output. Do not encode or decode during preflight.

- [ ] **Step 5: Start exactly one systemd invocation**

Use a uniquely named transient service, `Type=oneshot`, `RuntimeMaxSec=4h5m`, no restart, and the exact reviewed `--run` command. Record the unit name and invocation ID. Never restart the unit; a runner-level void/failure is final for G2.

- [ ] **Step 6: Wait for terminal state and capture provenance**

Monitor without altering the unit. Capture systemd result, exit code, runtime, CPU time, peak memory, swap, and journal. A non-success result or missing `TIMING-DONE.STAMP` is an instrument failure, not a measurement result.

### Task 6: Parse, review, and land the characterization result

**Files:**
- Create after a terminal valid run: `documentation/ephemeral/research/CUBR-DECODE-ATTRIB-RESULTS-20260809.md`
- Create evidence directory after a terminal valid run: `documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/`

- [ ] **Step 1: Verify evidence before reading performance values**

Verify completion-marker ordering, all SHA manifests, suite success, exact archive pairs, every `cmp`/original SHA, timeouts, stat agreement labels, G3 labels, process-exit gates, exact cell set, and systemd success. A failed cell remains failure/void; never substitute or estimate.

- [ ] **Step 2: Produce per-file attribution only**

Report the four cells separately. Calculate symbol buckets, IPC, misses/bit, cycles/bit only where allowed, and every component's Amdahl ceiling `1/(1-share)`. Evaluate P1-P5 exactly. Never compute a corpus-wide average or quote the profiling pin as benchmark throughput.

- [ ] **Step 3: Independent result/spec and quality reviews**

Use separate read-only subagents. Require exact raw-to-report reconciliation, honest ceilings, explicit perturbed/disagreement handling, and confirmation that the report characterizes where time goes without proposing a lever.

- [ ] **Step 4: Update only the existing NEW-24 note after review**

Prepare an independently reviewed, idempotent transaction that appends one exact pointer to the landed result report while keeping NEW-24 `in_progress`, leaving `measurements` empty, and leaving evaluation at zero. Pin the complete pre-state and verify exact post-state before execution.

- [ ] **Step 5: Land the result through a normal PR**

Commit raw evidence, parser output, report, and DB readback; run all checks; open a normal PR; wait for exact-head CI; merge; then fetch and verify current `origin/main`. Only after this closure may the next stage select and preregister a NEW-24 Fast-CM candidate from the measured attribution.
