# CUBR Zero-Representation Eight-Cell Matrix — Generation‑3 Preregistration Amendment

**State:** PREREGISTERED DESIGN — no implementation change, measurement, or result  
is recorded in this document. The amendment is committed before the corrected  
runner is built and before any cell is measured.

---

## 1. Amendment scope and motivation

Generation 2 of the cube campaign exited before any compression, warm‑up, or
timed decode because the clean‑tree admission gate failed. The integration test
suites unconditionally rewrote two JSON bench files that are tracked in the
repository. This amendment defines a **single runner fix** and re‑names the
generation‑3 campaign artefacts so that the original experiment can be executed
exactly once, without disturbing generation‑2 or generation‑1 output or logs.

No hypothesis, threshold, model, input, archive, binary, file order, schedule,
parser, DB mapping, round‑trip requirement, or Cargo‑path guard is altered.
The correction is purely a logical gate: the runner must detect the exact
expected side‑effect files, restore them from the committed HEAD version, and
then enforce tree cleanliness before entering the measurement phase.

---

## 2. Generation‑2 incident evidence

- **Campaign unit:** `cubr-zerorep-matrix-g2-20260809.service`
- **Launch time:** 2026‑08‑09T09:24:20 Z
- **Origin/main SHA:** `8630133718b268e8daddeb71db545ee849816844`
- **Suites:** both `cargo test --release` and
  `cargo test --release --test scheme_roundtrip` passed completely.
- **Clean‑tree failure:** after the suites, a `git status` check reported
  two modified tracked files:
  - `documentation/ephemeral/research/CUBR-0028-bench.json`
  - `documentation/ephemeral/research/CUBR-0031-bench.json`
  These files were unconditionally overwritten by the integration tests.
  No other untracked, deleted, or renamed entries were present. The gate
  aborted the campaign at 2026‑08‑09T09:27:33 Z before compression,
  warm‑up, or any timed decode. `results.tsv` and `roundtrips.tsv` contain
  headers only.
- The generation‑2 output root
  `/root/cubr-levers/zerorep-matrix-g2-20260809` remains untouched and must
  be preserved forever (see §7).

---

## 3. Invariants (zero scientific change)

Every parameter defined in the original preregistration
`CUBR-ZEROREP-MATRIX-20260809.md` §1–§12 is preserved without modification.
The generation‑3 campaign adheres to the identical:

- input files, canonical archives, binary hashes, and model table counts
- Latin‑square interleaving, per‑cell decode schedule, and timeout caps
- RSS and speed thresholds (reclaim fraction ≥ 0.75, residual ≤ 64 MiB,
  time ratio ≤ 1.05, speedup ≥ 1.10)
- accounting‑consistency label formulas
- void semantics and admission gates (host, load, bin identity, etc.)
- Database protocol — exactly 24 rows, run‑mode IDs
  `zerorep-<file>-<preset>-pin0-15-t4`, existing codec revision IDs 8, 9, 10,
  and the same transaction guarantees.

The only difference is the corrected runner and the new campaign identifiers
(checkout, output root, unit name). The G2 runner’s absolute‑Cargo and
source‑contract guards are unchanged and must pass identically.

---

## 4. Runner fix specification

The generation‑3 runner (to be placed at
`documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh`)
must contain **only** the following changes relative to the reviewed
generation‑2 runner:

1. After the last `cargo test` invocation exits successfully, but before the
   existing clean‑tree gate, insert a new code block that:
   a. Runs `git status --porcelain` exactly once; saves the output.
   b. Aborts immediately if the output contains any line whose status prefix
      is not exactly ` M` (space then M) or if any path does **not** match one
      of the two expected paths (exact string equality).
      Any missing, added (`??`), deleted, renamed, staged, or conflicting entry
      causes immediate abort with a descriptive message.
   c. Records the SHA‑256 of the modified version of each file as it exists
      on disk.
   d. Restores each file from the current HEAD revision using a safe
      two‑stage atomic write:
      - `git show HEAD:<path> > <path>.g3restore-tmp`
      - `mv <path>.g3restore-tmp <path>`
      The temporary file is on the same filesystem and is mode `0644`; the
      destination is replaced only after `git show` and hash verification
      succeed. Any leftover temporary path is dirty and therefore fatal.
   e. Re‑runs `git status --porcelain`; if output is non‑empty (any dirty
      entry remains), aborts.
   f. Re‑verifies the two restored files’ SHA‑256 against the known committed
      HEAD versions, hard-coded in the runner for immutability:
      - `CUBR-0028-bench.json`:
        `5d1313d8b3537ed276280ac587b3c94d181965fd35b60ac30b82c782e6b4ee1f`
      - `CUBR-0031-bench.json`:
        `98bc95cf2bf500c50f6f34887d4b02d078852795162f5ad884a3b7ab239e6c0b`
   g. Writes a single‑line evidence log in the output root
      `side-effect-restore.log` with the pre‑restore hashes, the exit code
      of the second `git status`, and the post‑restore hashes.

   The entire block must abort if any step fails. As in G2, the output root
   and header-only TSVs exist before the suite so suite/failure logs survive;
   no compression, warm-up, timing, verdict, or DONE marker may begin until
   restoration and the clean-tree gate pass.

2. Extend `--self-test` with the following regression tests, all of which
   must exit non‑zero when subject to the described mutation:
   a. Mutation: `git status --porcelain` returns a line for an unexpected
      path `unexpected.json`. Expected: aborts.
   b. Mutation: `git status --porcelain` returns a line with status prefix
      `??` for a known path. Expected: aborts.
   c. Mutation: `git status --porcelain` omits either expected path. Expected:
      exact-set classification aborts before restoration.
   d. Mutation: `git show HEAD:<path>` fails for one file. Expected: aborts.
   e. Mutation: `mv` command is removed; a subsequent `cmp` detects the
      file unchanged. Self‑test must catch that the file was not restored
      (original modification hash persists). Expected: aborts.
   f. Mutation: `git status --porcelain` after restore returns a non‑empty
      line (e.g., a stray untracked file). Expected: aborts.
   g. Mutation: one file’s restored hash does not match the hard‑coded
      committed hash. Expected: aborts.
   h. Mutation: the post-restore clean-tree function is removed or bypassed;
      a source-contract negative control must reject the mutated runner.
   i. Mutation: the `git status` command fails (e.g., `exit 1`). The
      check must treat that as fatal, not skip. Expected: aborts.

   j. Mutation: either the inherited `clean()` predicate or the
      `post_restore_clean_gate()` predicate is changed to accept dirt only when
      its root argument equals the live `ZERO_ROOT`. Expected: the source
      contract rejects the runner even though temporary-repository functional
      tests would otherwise pass.

   The self-test harness may use a temporary Git repository; it must not touch
   live campaign paths. The exact hard-coded committed hashes must be embedded
   in the runner and admission must verify them against `HEAD:<path>` before
   the suite.

   The source contract must freeze by SHA-256 three complete marker-bounded
   blocks: the full inherited `clean()` definition, the entire G3
   preservation/restoration helper block, and the live suite-restore through
   clean/rehash block. Each begin/end marker must occur exactly once and in
   order. Hashing only helper names or call lines is insufficient; every
   predicate/body line must be covered so dead-code decoys and live-root-only
   exceptions cannot balance the guard.

   Block contents alone do not prove top-level placement. The final source
   contract must also SHA-256 the entire runner after excluding exactly one
   `readonly FULL_SOURCE_CONTRACT_SHA256=...` line, require that line to occur
   once, and compare with the frozen digest. This normalized full-source guard
   must reject wrapping the intact live block in `if false; then ... fi`, even
   if a compensating line is removed elsewhere. Block digests remain
   defense-in-depth.

The original generation‑2 runner remains untouched in the G2 checkout and
is never overwritten.

---

## 5. Admission gates (generation‑3)

All gates from the original preregistration (including the G2 absolute‑Cargo
guard and the G1 preservation-root check) apply verbatim. In addition,
**before** any compression or measurement step the runner must:

- After the `cargo test` suites, execute the tree‑clean restoration block
  described in §4, which serves as both admission gate and side‑effect
  correction.
- Assert that the generation‑3 output root
  `/root/cubr-levers/zerorep-matrix-g3-20260809` does **not** exist.
- Assert that the G2 output root still exists and that **all** preserved
  file hashes match the manifest in §7.
- Assert that the G1 output root still exists with the original five hashes
  and empty `timing_logs/` as frozen in the G2 amendment §7.

---

## 6. Exact launch command

After this amendment and the corrected runner land on `origin/main` and
undergo independent review, generate the generation‑3 candidate checkout:

```bash
git clone https://github.com/Arcanada-one/cubrim.git /root/cubr-levers/zerorep-matrix-g3-code
git -C /root/cubr-levers/zerorep-matrix-g3-code checkout --detach <resulting-main-sha>
```

Build the candidate binary, run the suite, and then launch once:

```bash
timeout 14400 systemd-run --wait --collect \
  --unit=cubr-zerorep-matrix-g3-20260809.service \
  --property=RuntimeMaxSec=7200 \
  /root/cubr-levers/zerorep-matrix-g3-code/documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh
```

The unit must not be started before the review is complete, and it may be
launched exactly once. No restart, no reuse of previous logs, no widening of
timeout envelopes.

---

## 7. Preservation of generation‑2 and generation‑1 artefacts

**Generation‑2 root** `/root/cubr-levers/zerorep-matrix-g2-20260809` is
immutable and must never be deleted, modified, or reused. The launch‑time
preservation manifest is:

```text
d32843c23b9540f01fc512b7e59dfd0d50ee7a4fdb9b90f0c85a81db590cea04  HASHES.tsv
113976d8d42347ef3fb5d64c103dcf9c080fea8cbce4e97363e4caf4958b39a6  cargo-test-release.log
630ac2f25e566bcb876f45a3d5d7c012c7bac5b273cd1d99ffc714ac7014bbc4  cargo-test-scheme-roundtrip.log
365837f292ec206257ecb1e1d98ff9a54efe8d43c3dfb3d86465d446524e9b7b  journal.log
544748ffc2ffbcd9218ff43f09b7292811d6ab00e1fad789105adfc5d31fd19f  results.tsv
7ae44fbaaaf4cf26cc68d1643cc49da562434914dbade295605aaf5972944cdf  roundtrips.tsv
```

The root also contains exactly one directory, `timing_logs/`, which is real
(not a symlink) and empty. **Generation‑1 root** remains exactly as frozen in
the G2 amendment §7 and must never be altered.

---

## 8. Reference documents

- Original preregistration:
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809.md`
- Generation‑2 amendment:
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809.md`
- Generation‑2 plan:
  `documentation/ephemeral/plans/CUBR-ZEROREP-MATRIX-G2-20260809-plan.md`
- Generation‑2 runner:
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809/zerorep-matrix-g2-run.sh`
- Generation‑3 runner (to be created):
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh`
- This amendment:
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809.md`

---

**No measurement result exists yet. The generation‑3 campaign must only be
launched after the amended runner has been independently reviewed and merged
into `origin/main`.**
