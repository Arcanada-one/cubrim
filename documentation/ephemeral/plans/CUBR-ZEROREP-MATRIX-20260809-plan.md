# CUBR Zero-Representation Eight-Cell Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development`
> to execute this plan one bounded task at a time, with specification review
> before code-quality review.

**Goal:** Execute the preregistered remaining eight zero-representation cells once,
publish per-cell evidence, and record exactly 24 valid measurement rows without
changing product code or any public surface.

**Architecture:** A tracked fail-closed Bash runner verifies immutable source,
binary, input, and canonical-archive identities, then launches all eight cells in
one fixed systemd campaign. A small embedded Python parser computes per-cell
medians and verdicts from 72 raw timed observations. Database publication is a
separate atomic, idempotent transaction after the evidence is independently
reviewed.

**Tech stack:** Bash, GNU coreutils/time, Python 3 standard library, systemd,
Rust/Cargo, PostgreSQL/psql, Git/GitHub protected PR flow.

---

- [x] 1. Audit and harden the pre‑registered matrix design
- [ ] 2. Create fail‑closed runner and static control seam
- [ ] 3. Test runner syntax, ShellCheck, control cases and TSV/verdict parser
- [ ] 4. Independent pre‑measurement review of preregistration & runner
- [ ] 5. Push preregistration + runner PR and merge normally
- [ ] 6. Fetch exact resulting `origin/main`
- [ ] 7. Create clean stand candidate checkout & fresh release build with reproducibility gates
- [ ] 8. Full release suite & mutation‑sensitive focused tests on measured source
- [ ] 9. Verify base and current packed checkout & binary identities
- [ ] 10. Verify all three input slices & all eight canonical archives
- [ ] 11. Launch one immutable systemd unit once under fixed limits
- [ ] 12. Retrieve raw evidence and per‑cell TSV
- [ ] 13. Compute eight per‑cell medians, product verdicts, and accounting labels — no aggregate
- [ ] 14. On void: journal only. On complete: prepare the atomic 24-row NEW-30 transaction without executing it
- [ ] 15. Independent evidence and transaction review
- [ ] 16. Execute the reviewed DB transaction, verify it, and integrate result evidence via PR
- [ ] 17. Verify exact resulting `origin/main` and close

---

## 1. Audit and harden the pre‑registered matrix design

- File: `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809.md`
- Check every identity (input, archive, binary, source) against the pinned campaign’s actual state.
  - Input SHA‑256s, canonical archive SHA‑256s and sizes from §2.
  - Model table counts and ceilings from §3.
  - Admission gates, measurement protocol, Latin‑square order, stop semantics, DB protocol (§7–§10).
- Must agree with the single‑cell zero‑rep product commit `f047523fcd…` and its `cm2.rs` blob `1594578c…`.
- If any discrepancy is found, fix the preregistration in a documentation‑only commit.
- Requirement: the design must state that the preregistration is committed before
  the campaign's fresh candidate build. The candidate product source already
  exists on `main`; this matrix introduces no new product-source commit.

## 2. Create fail‑closed runner and static control seam

**File:** `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809/zerorep-matrix-run.sh`
The runner is a bash script with **no placeholders**.  It must contain, in machine‑readable structure:

- Hard‑coded admission identities from the preregistration:
  - Host `dev-ai`, CPU mask `0-15`, threads=4, load‑avg threshold `<2.0`, no other `cubrim` pid.
  - Base binary commit `e70d1cdca6…` & SHA‑256 `a195c227…`.
  - Current packed commit `49e429e587…` & SHA‑256 `12eaff4d…`.
  - Candidate source identity (the zero‑rep product commit/`cm2.rs` blob) and expected binary SHA‑256 from a prior clean build (`771fdb0f…`).
  - Three input slices under `/root/cubr-levers/bench` (`nci.2m`,
    `dickens.2m`, `ooffice.2m`) - exact paths and SHA-256.
  - Eight canonical base archives under `/root/cubr-levers/preset-rss`, each
    with file, preset, size, and SHA-256.
- **Compress and warm‑up** per cell:
  1. Compress with base, current, zero‑rep → verify archive byte‑identical to canonical.
  2. One unmeasured decode warm‑up per binary, `cmp` checked.
  3. Three interleaved measured decodes (Latin square of order 3) per binary, each using `/usr/bin/time -v`.
- **Timeout caps:** compress 1800 s, decode 300 s per operation.
- **TSV output:** a single `results.tsv` with columns: `cell,step,sample,build,wall_s,peak_rss_kib`.
- **Round-trip audit:** a separate `roundtrips.tsv` receives one row only after
  each successful `cmp`, with cell, phase, sample, build, and `cmp=PASS`.
  Completion requires exactly 96 unique PASS rows: 24 warm-up and 72 timed.
- **Verdict parser** included inline, or tracked beside the runner, that reads the
  TSV and computes per-build medians, product conditions, and accounting labels.
- **Fail‑closed:** any gate failure, hash mismatch, `cmp` failure, timeout, non‑zero exit → clean exit 1 and *only* a journal line.
- **Suite admission:** before compression or timing, execute the full release
  suite and the focused scheme round-trip test in the exact candidate checkout,
  capture their complete logs, assert the source tree remains clean, and record
  exact pass/fail/ignored counts. The earlier mutation-sensitive evidence must
  also be present at its tracked path and match its committed blob.
- **Static control seam:** the script must accept `--self-test`, which validates
  contract tables, exact 72-row/order expectations, parser arithmetic, and
  positive/negative synthetic verdict cases without claiming any live admission,
  archive, or measurement gate. Its output must be labelled `SELF_TEST_ONLY`.

After writing, record the runner’s SHA‑256 inside the plan, but do not compute it here; state that it will be recorded from `git show`.

## 3. Test runner syntax, ShellCheck, control cases and TSV/verdict parser

- Run `shellcheck zerorep-matrix-run.sh` – zero warnings.
- Execute `bash zerorep-matrix-run.sh --self-test`:
  - Must exit 0, state `SELF_TEST_ONLY`, validate all eight contract rows, and
    produce no live-admission or archive-identity PASS claim.
  - Must validate the expected 96-row round-trip schedule (24 warm-up, 72 timed)
    and reject missing, duplicate, or non-PASS rows.
  - Synthetic inputs must yield specific known PASS and REFUTED outcomes
    (including non-positive `P` and one failed speed condition).
- Verify that the verdict parser’s arithmetic exactly matches the formulas in the preregistration (RSS and speed conditions).
- Commit the tested runner as a separate, runner‑only commit after the preregistration.

## 4. Independent pre‑measurement review

- Provide reviewer(s) with:
  - The matrix preregistration from the same proposed PR.
  - The complete runner source (with `--self-test` output).
  - ShellCheck pass.
- Review criteria: byte‑identity gates, fail‑closed behaviour, Latin‑square interleaving, timeout envelope, TSV format, verdict computation, void semantics, DB protocol alignment.
- Resolve all Critical and Important findings.  If any change touches the runner, recommit and re‑review before measurement.

## 5. PR preregistration + plan + runner only and merge normally

- Ensure the branch contains **only** the preregistration, this plan, and the runner; no product code touches.
- Open a PR; pass CI/lint/ShellCheck checks.
- Merge normally.  The merge commit is the **resulting main** that will be used for the campaign.

## 6. Fetch exact resulting `origin/main`

```bash
git fetch origin main
git rev-parse origin/main   # record SHA
git diff --check origin/main...HEAD   # run before merge; after merge compare the landed blobs
git show origin/main:documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809/zerorep-matrix-run.sh | sha256sum
```
Verify the runner blob matches the reviewed commit.  Record the resulting main SHA.

## 7. Create fresh clean stand candidate checkout & fresh release build with reproducibility gates

- On `dev-ai`, use a clean checkout at the preregistered path
  `/root/cubr-levers/zerorep-matrix-code`, from the exact `origin/main` SHA
  recorded above. The path must not pre-exist:

```bash
RESULTING_MAIN_SHA=$(git rev-parse origin/main)
git clone https://github.com/Arcanada-one/Cubrim.git /root/cubr-levers/zerorep-matrix-code
git -C /root/cubr-levers/zerorep-matrix-code checkout --detach "$RESULTING_MAIN_SHA"
```

- Verify `code/cubrim-rs/src/cm2.rs` SHA‑256 equals the preregistered zero‑rep product blob `1594578c…`.
- Build with the same rustc/cargo toolchain as the pinned campaign:

```bash
cd code/cubrim-rs
cargo build --release
sha256sum target/release/cubrim
```

- The resulting binary SHA‑256 must exactly match `771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20`.
  If not, abort and investigate – the binary is not reproducible and the campaign is void.
- Mark this checkout as the candidate source; no further source or binary modifications.

## 8. Full release suite & mutation‑sensitive focused tests on measured source

- On the candidate stand checkout:

```bash
cd code/cubrim-rs
cargo test --release
cargo test --release --test scheme_roundtrip
```

- Record the exact pass/fail/ignored counts.
- Run the two focused XOR‑bias tests individually (exact names) and require **GREEN**:

```bash
cargo test --release --lib ctr_zero_representation_starts_zero_and_predicts_midpoint
cargo test --release --lib ctr_zero_representation_update_preserves_logical_fields
```

- Perform mutation‑sensitivity proof exactly as in the original plan:
  1. Temporarily revert initialisation to non‑zero – red, revert – green.
  2. Temporarily remove read‑side XOR – red, revert – green.
  3. Temporarily remove write‑side XOR – red, revert – green.
  (Each surgical edit must leave the tree clean afterwards.)
- All outputs must be captured; the final tree must be identical to the committed candidate source.

## 9. Verify base and current packed checkout & binary identities

- Reuse the already clean, pinned baseline and current checkouts after verifying
  their exact commits, clean status, and binary hashes. Do not rebuild them:

```bash
git -C /root/cubr-levers/zerorep-baseline-e70 rev-parse HEAD
git -C /root/cubr-levers/zerorep-baseline-e70 status --porcelain
sha256sum /root/cubr-levers/zerorep-baseline-e70/code/cubrim-rs/target/release/cubrim

git -C /root/cubr-levers/zerorep-current-49e rev-parse HEAD
git -C /root/cubr-levers/zerorep-current-49e status --porcelain
sha256sum /root/cubr-levers/zerorep-current-49e/code/cubrim-rs/target/release/cubrim
```

- Do not rebuild the candidate binary again – reuse the one from step 7.

## 10. Verify all three input slices & all eight canonical archives

- Input slices (`/root/cubr-levers/bench/nci.2m`, `dickens.2m`,
  `ooffice.2m`) - verify SHA-256.
- For each of the eight cells, compress with the base binary and verify the
  output archive SHA-256 and size exactly match the canonical entries from §2.
- Also verify that the same input compressed with current‑packed and candidate binaries produces byte‑identical archives to those canonical ones (no need to re‑SHA‑256 each time, just `cmp`).
- Any mismatch → campaign void.

## 11. Launch one immutable systemd unit once under fixed limits

- Ensure `/root/cubr-levers/zerorep-matrix-code` exists and output root `/root/cubr-levers/zerorep-matrix-20260809` does **not** exist.
- Execute exactly:

```bash
timeout 14400 systemd-run --wait --collect \
  --unit=cubr-zerorep-matrix-20260809.service \
  --property=RuntimeMaxSec=7200 \
  /root/cubr-levers/zerorep-matrix-code/documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809/zerorep-matrix-run.sh
```

- The runner’s first act must be to check admission (load, no competing process, CPU mask, etc.).
- No parameter changes, no manual intervention.  If the unit fails or times out, treat as void.

## 12. Retrieve raw evidence and per‑cell TSV

- After unit finishes, collect from `/root/cubr-levers/zerorep-matrix-20260809/`:
  - `results.tsv` (timed samples).
  - `roundtrips.tsv` (all successful warm-up and timed `cmp` checks).
  - `timing_logs/*.log` for every `time -v` output.
  - `verdict.json` generated by the verdict parser if the campaign completed.
- Verify that the number of TSV rows matches 8 cells × (9 measured decodes) = 72 rows.
- Verify `roundtrips.tsv` has exactly 96 unique PASS rows: 24 warm-up and
  72 timed, with every expected cell/sample/build tuple present exactly once.
- Check that no cell timed out; any timeout voids the whole campaign.

## 13. Compute eight per‑cell medians, product verdicts, and accounting labels — no aggregate

If the campaign completed, the runner’s parser already produced per‑cell medians and verdicts.  Manually re‑verify:

- For each cell, from the TSV, extract three samples per build, compute median `wall_s` and `peak_rss_kib`.
- Apply the four product conditions (R/P≥0.75, zero‑base≤65536 KiB, time ratio≤1.05, speedup≥1.10) as defined in §4.
- Determine PASS/REFUTED per cell.
- Compute accounting labels: if R≤T and B≤E (where relevant) mark `ACCOUNTING_CONSISTENT`, else `EXPLANATION_INCOMPLETE`.
- **No per‑corpus aggregate, no averaging, no estimation.**
- Document the findings in a markdown file `CUBR-ZEROREP-MATRIX-20260809-results.md` placed in the same ephemeral/research directory.

## 14. On void: journal only. On complete: prepare the atomic 24-row NEW-30 transaction without executing it

- If the campaign is void (any gate fail, timeout, `cmp` fail, binary mismatch, incomplete TSV), write a journal entry in `/root/cubr-levers/zerorep-matrix-20260809/journal.md` and **do not touch the database**.
- If complete (72 valid timings, all gates passed, medians computed), prepare
  the database transaction but do not execute it before independent review:

  1. Verify that hypothesis **NEW-30** exists and that exactly zero rows exist in
     `web_benchmark_hypothesis_evaluation` after joining through
     `web_benchmark_hypothesis.task_id='NEW-30'`; do not mutate that table.
  2. Confirm zero rows exist in NEW‑30 for any of the eight run‑mode IDs:
     `zerorep-nci-balanced-pin0-15-t4`, `zerorep-nci-web-pin0-15-t4`,
     `zerorep-dickens-max-pin0-15-t4`, `zerorep-dickens-balanced-pin0-15-t4`,
     `zerorep-dickens-web-pin0-15-t4`,
     `zerorep-ooffice-max-pin0-15-t4`, `zerorep-ooffice-balanced-pin0-15-t4`,
     `zerorep-ooffice-web-pin0-15-t4`.
  3. Prepare an atomic transaction:
     - For each cell, insert three rows (one per build) with:
       - `run_mode` = appropriate identifier.
       - `codec_rev` = the verified existing integer foreign key: baseline 9,
         current 8, or zero-representation 10. Before mutation, assert those IDs
         map respectively to `codec_revisions.sha` values
         `cli-sha256:a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd`,
         `cli-sha256:12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c`,
         and
         `cli-sha256:771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20`.
       - `corpus_file` = `silesia/<file>[0:2097152]`.
       - `orig_bytes=2097152`, `comp_bytes` = the pinned archive size,
         `ratio=comp_bytes/2097152`, `rt_ok=true`, `host=dev-ai`, and
         `cpu_pin=0-15`.
       - `decode_ms` = median decode milliseconds (converted from wall_s).
       - `decode_peak_rss_kib` = median peak RSS.
       - `duration_ms`, `peak_rss_kib` left NULL (encode fields).
     - Total 24 rows. Do not write `web_benchmark_hypothesis_evaluation`.
  4. Before commit, assert exactly 24 rows exist for the eight new run modes,
     all required identity/round-trip/decode fields match, encode fields are
     null, and the exact NEW-30 evaluation-row query remains zero.
     Rollback on any failure.
  5. Extend `hypotheses.measure_note` once, using an exact idempotency marker,
     with the eight per-cell product labels and accounting labels.
  6. Include an idempotent replay path: identical rows and note cause no change;
     any partial or conflicting state aborts.

- The operation must be performed in a single bash/python script using the DB CLI, with error handling that does not leave partial rows.

## 15. Independent evidence and transaction review

- Provide a reviewer with:
  - The complete raw evidence (timing logs, TSV, verdict JSON).
  - The manual recomputed medians and verdicts.
  - The proposed DB transaction script, not yet executed.
  - The resulting main commit and all hash verifications.
- Review must confirm:
  1. No drift from preregistered identities.
  2. All product gates correctly applied.
  3. No aggregate or extrapolation.
  4. Proposed DB rows match medians and run-mode IDs.
  5. Accounting labels are honest and match formulas.
  6. No site or public‑facing action taken.
- Resolve any issues before final integration.

## 16. Execute the reviewed DB transaction, verify it, and integrate result evidence via PR

- Execute the independently approved transaction once. Capture its transaction
  output and a fresh scoped readback.
- Replay the same script and require zero inserted rows, zero note changes, and
  the same exact 24-row readback.
- Dispatch an independent post-mutation check of the transaction output and DB
  readback before opening or merging the evidence PR.

- Prepare a PR that adds only:
  - `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809-results.md` (the per‑cell verdicts, medians, and labels).
  - Optionally a compressed tarball of the timing logs (if policy permits) in an appropriate location.
- The PR must not modify product code; it is evidence only.
- After review, merge normally.  Do not push to site or update leaderboard.

## 17. Verify exact resulting `origin/main` and close

- Fetch merged main:

```bash
git fetch origin main
git rev-parse origin/main
git diff --stat origin/main...prior-resulting-main
```

- The diff must contain only the results file and optional tar; no other changes.
- Confirm the DB remains as committed (read back the 24 rows).
- Mark the eight‑cell matrix experiment closed only after all the above hold.
- Do not claim closure of the overall NEW‑30 lever or the zero‑rep work; the matrix is one portion.

---

**This plan is executable with the given preregistration; no product‑code change, no TBD, and no site cycles.**
