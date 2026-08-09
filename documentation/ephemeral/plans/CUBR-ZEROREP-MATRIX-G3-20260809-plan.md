**CUBR-ZEROREP-MATRIX-G3-20260809 · Generation‑3 Eight-Cell Matrix Execution Plan Amendment**

This document amends the original **CUBR Zero-Representation Eight-Cell Matrix
Implementation Plan** (`CUBR-ZEROREP-MATRIX-20260809-plan.md`) to incorporate the
**Generation‑3 Preregistration Amendment**
(`CUBR-ZEROREP-MATRIX-G3-20260809.md`).  All scientific parameters, identities,
measurement protocol, and DB protocol remain exactly as defined in the
original preregistration and plan.  The amendment introduces **only** a
side‑effect classifier and tree‑restoration block after the test suites, with
its own regression self‑tests, and uses distinct generation‑3 artefacts; no
product code is changed.

- [x] 1. Preserve generation‑1 and generation‑2 artefacts and document the g2 incident
- [ ] 2. Commit the generation‑3 preregistration amendment and plan before code
- [ ] 3. Add the corrected G3 runner with side‑effect restoration and self‑tests
- [ ] 4. Complete independent spec and quality reviews
- [ ] 5. Merge the G3‑only PR and fetch the exact resulting `origin/main`
- [ ] 6. Create a clean stand‑alone candidate checkout, build, and verify identities
- [ ] 7. Execute self‑test under a `PATH` that excludes `/root/.cargo/bin`
- [ ] 8. Launch the generation‑3 systemd unit exactly once
- [ ] 9. Retrieve and independently validate generation‑3 evidence
- [ ] 10. Prepare and review the atomic 24‑row NEW‑30 DB transaction
- [ ] 11. Execute and verify the reviewed DB transaction idempotently
- [ ] 12. Integrate result evidence via a documentation‑only PR and close the G3 matrix

---

### 1. Generation‑2 side‑effect incident (preservation complete)

- The `cubr-zerorep-matrix-g2-20260809.service` unit launched at 2026‑08‑09T09:24:20 Z.
- Both `cargo test --release` and `cargo test --release --test scheme_roundtrip`
  completed entirely, but the clean‑tree gate failed because two tracked bench
  files were overwritten unconditionally:
  - `documentation/ephemeral/research/CUBR-0028-bench.json`
  - `documentation/ephemeral/research/CUBR-0031-bench.json`
- The runner aborted before any compression, warm‑up, or timed decode.
- The generation‑2 output root `/root/cubr-levers/zerorep-matrix-g2-20260809`
  is preserved, immutable, and must **never** be deleted, modified, or reused.
  Its manifest (frozen in the G2 amendment §7):
  ```text
  d32843c23b9540f01fc512b7e59dfd0d50ee7a4fdb9b90f0c85a81db590cea04  HASHES.tsv
  113976d8d42347ef3fb5d64c103dcf9c080fea8cbce4e97363e4caf4958b39a6  cargo-test-release.log
  630ac2f25e566bcb876f45a3d5d7c012c7bac5b273cd1d99ffc714ac7014bbc4  cargo-test-scheme-roundtrip.log
  365837f292ec206257ecb1e1d98ff9a54efe8d43c3dfb3d86465d446524e9b7b  journal.log
  544748ffc2ffbcd9218ff43f09b7292811d6ab00e1fad789105adfc5d31fd19f  results.tsv
  7ae44fbaaaf4cf26cc68d1643cc49da562434914dbade295605aaf5972944cdf  roundtrips.tsv
  ```
  The directory `timing_logs/` is real (not a symlink) and empty.
- The generation‑1 output root `/root/cubr-levers/zerorep-matrix-20260809`
  remains exactly as frozen in the G2 amendment §7, and is never altered.
- All hashes above have been verified against the immutable G1 and G2
  preservation manifests. ✔

### 2. Amendment scope (only tree‑restoration gate)

  - The G3 runner (`zerorep-matrix-g3-run.sh`) will contain **exactly** the
    changes described in `CUBR-ZEROREP-MATRIX-G3-20260809.md` §4‑§5, which
    are:
    - After the last `cargo test` invocation succeeds, insert a block that:
      - runs `git status --porcelain` and aborts on any unexpected or
        non‑modified-tracked lines,
      - records SHA‑256 of the current (modified) versions of the two known
        side‑effect files,
      - restores each file from the current HEAD via a safe two‑stage atomic
        write (`git show HEAD:<path> > <path>.g3restore-tmp` then
        `mv <path>.g3restore-tmp <path>`),
      - re‑runs `git status --porcelain` and aborts if tree is not pristine,
      - verifies restored SHA‑256 against hard‑coded committed HEAD hashes,
      - writes a single‑line evidence log `side-effect-restore.log` in the
        output root with pre‑restore hashes, the exit code of the second
        `git status`, and the post‑restore hashes.
    - Extend `--self-test` with the mutation tests (a-j) listed in the
      amendment §4.2, covering unexpected paths, missing files, `git show`
      failure, restore not applied, stray untracked file, hash mismatch,
      skipped tree check, `git status` failure, and live-root-only clean-gate
      bypasses.
    - Freeze complete marker-bounded SHA-256 blocks for the inherited clean
      helper, every restoration helper body, and the live restore/clean/rehash
      sequence; require unique ordered markers and reject decoy copies.
    - Freeze the normalized full runner source, excluding exactly one
      self-digest constant line, so intact-block relocation or surrounding
      `if false` wrappers cannot preserve the contract.
    - No other logic, admission gates, or paths are changed; the G3 runner
      renames all checkpoint paths to use `g3` identifiers.
  - All other gates, identities, timings, and DB protocol are strictly and
    exclusively those of the original preregistration and original plan.

### 3. Checklist and exact commands

Only the amended steps are listed; any step not repeated here is executed
identically to the original plan using the new generation‑3 paths and names.

- [x] 1. **Preserve generation‑1 and generation‑2 artefacts and document the g2 incident**
  - Verify all G1 and G2 file hashes against the immutable manifests in the
    G2 amendment §7 and the present plan §1.
  - Document the incident in this plan (already done in §1).

- [ ] 2. **Commit the generation‑3 preregistration amendment and plan before code**
  - Branch from the freshly fetched `origin/main` tip.
  - Commit only the two G3 markdown files. Do not add the runner until this
    preregistration commit exists.

- [ ] 3. **Add the corrected G3 runner**
  - The final branch must add **only** the two G3 markdown files and
    `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh`.
  - The runner must be created by copying the G2 runner (preserving all its
    absolute‑Cargo and source‑contract guards), then:
    - updating all campaign‑specific paths and names to `g3`,
    - inserting the tree‑restoration block exactly as per the amendment §4,
    - embedding the hard‑coded committed HEAD hashes of the two bench files
      as they exist on the official checkout:
      `5d1313d8b3537ed276280ac587b3c94d181965fd35b60ac30b82c782e6b4ee1f`
      and `98bc95cf2bf500c50f6f34887d4b02d078852795162f5ad884a3b7ab239e6c0b`,
    - extending `--self-test` with the nine mutation‑regression tests.
  - The runner must be executable, pass ShellCheck, and its `--self-test` must
    exit with 0 only when all original G2 contract checks (including the
    absolute‑cargo occurrence contract) plus the new G3 tree‑restoration
    simulations succeed.
  - Record the script’s SHA‑256 after commit: `git show HEAD:documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh | sha256sum`

- [ ] 4. **Independent spec‑ and quality‑review**
  - Provide reviewer(s) with:
    - The G3 preregistration amendment and this plan.
    - The full G3 runner source.
    - Output of `bash zerorep-matrix-g3-run.sh --self-test` run under a
      `PATH` that excludes `/root/.cargo/bin` (i.e.
      `PATH=/usr/sbin:/usr/bin:/sbin:/bin`); it must exit 0 and print
      `SELF_TEST_ONLY`.
  - Resolve all Critical and Important findings before merging.

- [ ] 5. **Merge and fetch exact resulting `origin/main`**
  - Push the G3‑only PR, pass CI/lint/ShellCheck, merge normally.
    The merge commit is the **resulting main** for the campaign.
  ```bash
  git fetch origin main
  git rev-parse origin/main              # record G3_RESULTING_MAIN_SHA
  git show origin/main:documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh | sha256sum
  ```
  - The runner blob must match the reviewed commit exactly.

- [ ] 6. **Clean checkout, build, and identity verification**
  ```bash
  G3_RESULTING_MAIN_SHA=$(git rev-parse origin/main)
  # Ensure the G3 code path does not pre‑exist; if it does, abort.
  git clone https://github.com/Arcanada-one/cubrim.git /root/cubr-levers/zerorep-matrix-g3-code
  git -C /root/cubr-levers/zerorep-matrix-g3-code checkout --detach "$G3_RESULTING_MAIN_SHA"
  ```
  - Verify `code/cubrim-rs/src/cm2.rs` SHA‑256 equals the original
    preregistered zero‑rep product blob `1594578c…`.
  - Build only with the absolute `cargo`:
    ```bash
    cd /root/cubr-levers/zerorep-matrix-g3-code/code/cubrim-rs
    /root/.cargo/bin/cargo build --release
    sha256sum target/release/cubrim
    ```
  - The binary SHA‑256 must exactly match `771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20` (the zero‑rep binary from the original campaign).  Any mismatch aborts the G3 campaign as void.

- [ ] 7. **Self‑test under a `PATH` that excludes `/root/.cargo/bin`**
  ```bash
  env PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    bash /root/cubr-levers/zerorep-matrix-g3-code/documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh --self-test
  ```
  - Must print `SELF_TEST_ONLY` and exit 0.  Any failure is a void for the campaign.

- [ ] 8. **Launch the distinct generation‑3 systemd unit**
  - Assert that the G3 output root `/root/cubr-levers/zerorep-matrix-g3-20260809`
    does **not** exist.
  - Assert that all G1 and G2 file hashes still match their respective
    manifests (G1 frozen in G2 amendment §7, G2 as listed in §1 of this plan).
  - Assert that the G2 output root still contains exactly the six hashed files
    plus the empty `timing_logs/` directory.
  - Launch exactly once, with the exact command from the amendment §6:
    ```bash
    timeout 14400 systemd-run --wait --collect \
      --unit=cubr-zerorep-matrix-g3-20260809.service \
      --property=RuntimeMaxSec=7200 \
      /root/cubr-levers/zerorep-matrix-g3-code/documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh
    ```

- [ ] 9. **Retrieve and validate generation‑3 evidence**
  - From `/root/cubr-levers/zerorep-matrix-g3-20260809/` collect:
    - `results.tsv` – header plus 72 data rows (8 cells × 9 measured decodes).
    - `roundtrips.tsv` – header plus exactly 96 unique PASS data rows
      (24 warm-up + 72 timed).
    - `timing_logs/*.log` – 72 timed logs plus 24 warm-up stderr logs.
    - `side-effect-restore.log` – as written by the restoration block.
    - `journal.log` – campaign journal (if campaign completed).
    - `verdict.json` if the campaign completed.
  - Any timeout, missing row, or `cmp` failure voids the whole G3 campaign.

- [ ] 9a. **Compute per‑cell medians and verdicts**
  - If the campaign completed, re‑verify the medians and product verdicts exactly
    as described in the original plan §13, using the identical formulas from the
    preregistration.
  - On void: write a journal entry in
    `/root/cubr-levers/zerorep-matrix-g3-20260809/journal.log` and **do not
    touch the database**.

- [ ] 10. **Prepare the atomic 24‑row NEW‑30 DB transaction**
  - Only if the campaign is complete and all gates passed.
  - Follow the original plan §14 identically, using the same run‑mode IDs,
    codec revision IDs (baseline 9, current 8, zero‑rep 10), and the same
    transaction script with idempotent replay protection.  **No row is
    inserted before independent review.**

- [ ] 10a. **Independent evidence and DB‑transaction review**
  - Provide reviewer(s) with the complete G3 evidence, recomputed medians,
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
    - `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809-results.md`
    - Optionally a compressed tarball of timing logs.
  - After review and merge, verify `origin/main` diff contains only the
    evidence files.
  - Mark the G3 matrix experiment closed.  The overall NEW‑30 lever and
    zero‑rep work remain open.

---

**The generation‑1 and generation‑2 artefacts are immutable; the generation‑3 campaign must only be launched after the amended runner is independently reviewed and merged.  This plan contains no invented results.**
