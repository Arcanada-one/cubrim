**CUBR-ZEROREP-MATRIX-G2-20260809 · Generation‑2 Eight-Cell Matrix Execution Plan Amendment**

This document amends the original **CUBR Zero-Representation Eight-Cell Matrix
Implementation Plan** (`CUBR-ZEROREP-MATRIX-20260809-plan.md`) to incorporate the
**Generation‑2 Preregistration Amendment**
(`CUBR-ZEROREP-MATRIX-G2-20260809.md`).  All scientific parameters, identities,
measurement protocol, and DB protocol remain exactly as defined in the
original preregistration and plan.  The amendment introduces **only** a
fail‑closed runner that uses an absolute `cargo` path, a regression self‑test,
and distinct generation‑2 artefacts; no product code is changed.

- [x] 1. Preserve generation‑1 artefacts and record the failure
- [x] 2. Commit the generation‑2 preregistration amendment and plan before code
- [ ] 3. Add the corrected G2 runner and regression test
- [ ] 4. Complete independent spec and quality reviews
- [ ] 5. Merge the G2-only PR and fetch the exact resulting `origin/main`
- [ ] 6. Create a clean stand-alone candidate checkout, build, and verify identities
- [ ] 7. Execute self-test under a `PATH` that excludes `/root/.cargo/bin`
- [ ] 8. Launch the generation‑2 systemd unit exactly once
- [ ] 9. Retrieve and independently validate generation‑2 evidence
- [ ] 10. Prepare and review the atomic 24-row NEW-30 DB transaction
- [ ] 11. Execute and verify the reviewed DB transaction idempotently
- [ ] 12. Integrate result evidence via a documentation-only PR and close the G2 matrix

---

### 1. Generation‑1 pre‑measurement failure

- The `cubr-zerorep-matrix-20260809.service` unit launched at 2026‑08‑09T08:13:43 Z.
- The runner’s admission/self‑test phase reached line 215, which invoked bare
  `cargo`.  The transient unit’s `PATH` did **not** contain
  `/root/.cargo/bin`, so the command failed with “command not found”.
- No compression, warm-up, or timed decode ran; the two result TSVs contain
  headers only. The five preserved files and their SHA-256 values are frozen
  in the G2 preregistration amendment §7.
- The output root `/root/cubr-levers/zerorep-matrix-20260809` is forever
  preserved, immutable, and must **never** be reused, modified, or deleted.

### 2. Amendment scope (one root‑cause fix)

  - The G2 runner (`zerorep-matrix-g2-run.sh`) will contain **exactly** the
  changes described in `CUBR-ZEROREP-MATRIX-G2-20260809.md` §4-§5:
  - Declare `readonly CARGO=/root/.cargo/bin/cargo`.
  - Verify it is executable and reports version `cargo 1.96.1`.
  - Replace every bare `cargo` invocation with `"$CARGO"`.
  - Extend `--self-test` with the exact whole-source occurrence contract; only
    the two lowercase tokens in `/root/.cargo/bin/cargo` are permitted.
  - Assert the two exact full suite lines use `"$CARGO"` in command position;
    reject quoted, braced, or unquoted `$CARGO_PROGRAM` in command position and
    freeze the reviewed total identifier count.
  - Make checkout cleanliness fail closed when `git status` errors.
  - Enforce the exact G1 preservation root before the Rust suite: five hashed
    files plus one real, empty `timing_logs/` directory.
- All other gates, identities, timings, and DB protocol are strictly and
  exclusively those of the original preregistration and original plan.

### 3. Checklist and exact commands

Only the amended steps are listed; any step not repeated here is executed
identically to the original plan using the new generation‑2 paths and names.

- [x] 1. **Preserve generation‑1 artefacts and record the failure**
  - Verify all five hashes against the immutable manifest in the G2
    preregistration amendment §7.
  - Document the failure in this plan (already done in §1).

- [ ] 2. **Commit the generation‑2 preregistration amendment and plan before code**
  - Branch from the freshly fetched `origin/main` tip.
  - Commit only the two G2 markdown files. Do not add the runner until this
    preregistration commit exists.

- [ ] 3. **Add the corrected G2 runner**
  - The final branch must add **only** the two G2 markdown files and
    `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809/zerorep-matrix-g2-run.sh`.
  - The runner must be executable, pass ShellCheck, and contain the regression
    self‑test described in the amendment.
  - Mutation tests must reject the reviewer examples `if cargo`, `! cargo`,
    `( cargo )`, `time cargo`, `command cargo`, and `env X=1 cargo`.
  - Mutation tests must also replace each absolute suite invocation with
    `"$CARGO_PROGRAM"` independently and reject both variants.
  - A combined mutation that replaces both live invocations and places the two
    expected lines in an `if false; then ... fi` decoy block must be rejected.
  - A failing `git status` probe must be rejected, never interpreted as clean.
  - A missing, changed, extra, symlinked, or non-empty G1 entry must be rejected
    before the Rust suite; the only directory allowed is empty `timing_logs/`.
  - Commit message: “Add generation‑2 zero‑rep matrix amendment, plan, and runner”
  - Record the script’s SHA‑256 after commit: `git show HEAD:… | sha256sum`

- [ ] 4. **Independent spec‑ and quality‑review**
  - Provide reviewer(s) with:
    - The G2 preregistration amendment and this plan.
    - The full G2 runner source.
    - Output of `bash zerorep-matrix-g2-run.sh --self-test` run under a
      `PATH` that excludes `/root/.cargo/bin` (i.e.
      `PATH=/usr/sbin:/usr/bin:/sbin:/bin`); it must exit 0 and print
      `SELF_TEST_ONLY`.
  - Resolve all Critical and Important findings before merging.

- [ ] 5. **Merge and fetch exact resulting `origin/main`**
  - Push the G2‑only PR, pass CI/lint/ShellCheck, merge normally.  
    The merge commit is the **resulting main** for the campaign.
  ```bash
  git fetch origin main
  git rev-parse origin/main              # record G2_RESULTING_MAIN_SHA
  git show origin/main:documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809/zerorep-matrix-g2-run.sh | sha256sum
  ```
  - The runner blob must match the reviewed commit exactly.

- [ ] 6. **Clean checkout, build, and identity verification**
  ```bash
  G2_RESULTING_MAIN_SHA=$(git rev-parse origin/main)
  # Ensure the G2 code path does not pre-exist; if it does, abort.
  git clone https://github.com/Arcanada-one/cubrim.git /root/cubr-levers/zerorep-matrix-g2-code
  git -C /root/cubr-levers/zerorep-matrix-g2-code checkout --detach "$G2_RESULTING_MAIN_SHA"
  ```
  - Verify `code/cubrim-rs/src/cm2.rs` SHA‑256 equals the original
    preregistered zero‑rep product blob `1594578c…`.
  - Build only with the absolute `cargo`:
    ```bash
    cd /root/cubr-levers/zerorep-matrix-g2-code/code/cubrim-rs
    /root/.cargo/bin/cargo build --release
    sha256sum target/release/cubrim
    ```
  - The binary SHA‑256 must exactly match `771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20` (the zero‑rep binary from the original campaign).  Any mismatch aborts the G2 campaign as void.

- [ ] 7. **Self‑test under a `PATH` that excludes `/root/.cargo/bin`**
  ```bash
  # Explicitly strip cargo's bin directory to prove the runner never invokes bare cargo.
  env PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    bash /root/cubr-levers/zerorep-matrix-g2-code/documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809/zerorep-matrix-g2-run.sh --self-test
  ```
  - Must print `SELF_TEST_ONLY` and exit 0.  Any failure is a void for the campaign.

- [ ] 8. **Launch the distinct generation‑2 systemd unit**
  - Assert that the G2 output root `/root/cubr-levers/zerorep-matrix-g2-20260809`
    does **not** exist.
  - Assert that all five G1 file hashes still match the amendment §7 manifest.
  - Launch exactly once, with the exact command from the amendment §6:
    ```bash
    timeout 14400 systemd-run --wait --collect \
      --unit=cubr-zerorep-matrix-g2-20260809.service \
      --property=RuntimeMaxSec=7200 \
      /root/cubr-levers/zerorep-matrix-g2-code/documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809/zerorep-matrix-g2-run.sh
    ```

- [ ] 9. **Retrieve and validate generation‑2 evidence**
  - From `/root/cubr-levers/zerorep-matrix-g2-20260809/` collect:
    - `results.tsv` – must have 72 rows (8 cells × 9 measured decodes).
    - `roundtrips.tsv` – exactly 96 unique PASS rows (24 warm‑up + 72 timed).
    - `timing_logs/*.log` – one per timed decode.
    - `verdict.json` if the campaign completed.
  - Any timeout, missing row, or `cmp` failure voids the whole G2 campaign.

- [ ] 9a. **Compute per‑cell medians and verdicts**
  - If the campaign completed, re‑verify the medians and product verdicts exactly
    as described in the original plan §13, using the identical formulas from the
    preregistration.
  - On void: write a journal entry in
    `/root/cubr-levers/zerorep-matrix-g2-20260809/journal.log` and **do not
    touch the database**.

- [ ] 10. **Prepare the atomic 24‑row NEW‑30 DB transaction**
  - Only if the campaign is complete and all gates passed.
  - Follow the original plan §14 identically, using the same run‑mode IDs,
    codec revision IDs (baseline 9, current 8, zero‑rep 10), and the same
    transaction script with idempotent replay protection.  **No row is
    inserted before independent review.**

- [ ] 10a. **Independent evidence and DB‑transaction review**
  - Provide reviewer(s) with the complete G2 evidence, recomputed medians,
    proposed transaction, and identity‑verification logs.
  - Confirm no drift, correct per‑cell labels, accounting‑consistency
    formulas, and no site/public action.

- [ ] 11. **Execute the reviewed DB transaction idempotently**
  - Run the approved script once, capture its output, and verify exactly 24
    rows are present for the eight new run modes.
  - Replay the script and require zero inserted rows, zero note changes, and
    an identical readback.  Any partial or conflicting state must rollback.

- [ ] 12. **Integrate evidence and close**
  - Open a documentation‑only PR that adds:
    - `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809-results.md`
    - Optionally a compressed tarball of timing logs.
  - After review and merge, verify `origin/main` diff contains only the
    evidence files.
  - Mark the G2 matrix experiment closed.  The overall NEW‑30 lever and
    zero‑rep work remain open.

---

**The generation‑1 artefacts are immutable; the generation‑2 campaign must only be launched after the amended runner is independently reviewed and merged.  This plan contains no invented results.**
