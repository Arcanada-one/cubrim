# CUBR Zero-Representation Eight-Cell Matrix — Generation‑2 Preregistration Amendment

**State:** PREREGISTERED DESIGN — no implementation change, measurement, or result  
is recorded in this document. The amendment is committed before the corrected  
runner is built and before any cell is measured.

---

## 1. Amendment scope and motivation

The original preregistration `CUBR-ZEROREP-MATRIX-20260809.md` and all  
scientific parameters, measurements, and product code remain unchanged.  
Generation 1 of the campaign (`cubr-zerorep-matrix-20260809.service`) exited  
before any warm‑up or timed decode because line 215 of the runner invoked bare  
`cargo` and the transient systemd unit’s `PATH` omitted `/root/.cargo/bin`.  
This amendment defines a **single runner fix** and re‑names the generation‑2  
campaign artefacts so that the original experiment can be executed exactly once,  
without disturbing generation‑1 output or logs.

No hypothesis, threshold, model, input, archive, binary, file order, schedule,  
parser, DB mapping, or round‑trip requirement is altered. The correction is  
purely environmental: the runner must use an absolute `cargo` path.

---

## 2. Generation‑1 incident evidence

- **Campaign unit:** `cubr-zerorep-matrix-20260809.service`  
- **Launch time:** 2026‑08‑09T08:13:43 Z  
- **Exited before any cell warm‑up:** admission completed, then runner line 215
  invoked `cargo test --release` without a full path.  
  The transient systemd unit’s `PATH` did not contain `/root/.cargo/bin`,  
  causing a “command not found” error.  
- The whole campaign voided immediately — no compression, warm-up, or timed
  decode ran. `results.tsv` and `roundtrips.tsv` contain headers only. The
  preserved root contains `HASHES.tsv`, `cargo-test-release.log`,
  `journal.log`, and those two header-only TSV files.
- The generation‑1 output root `/root/cubr-levers/zerorep-matrix-20260809`  
  remains untouched and must be preserved forever (see §7).

---

## 3. Invariants (zero scientific change)

Every parameter defined in `CUBR-ZEROREP-MATRIX-20260809.md` §1–§12 is preserved  
without modification. The generation‑2 campaign adheres to the identical:

- input files, canonical archives, binary hashes, and model table counts  
- Latin‑square interleaving, per‑cell decode schedule, and timeout caps  
- RSS and speed thresholds (reclaim fraction ≥ 0.75, residual ≤ 64 MiB,  
  time ratio ≤ 1.05, speedup ≥ 1.10)  
- accounting‑consistency label formulas  
- void semantics and admission gates (host, load, bin identity, etc.)  
- Database protocol — exactly 24 rows, run‑mode IDs  
  `zerorep-<file>-<preset>-pin0-15-t4`, existing codec revision IDs 8, 9, 10,  
  and the same transaction guarantees.

The only difference is the corrected runner file and the new campaign  
identifiers (checkout, output root, unit name).

---

## 4. Runner fix specification

The generation‑2 runner (to be placed at  
`documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809/zerorep-matrix-g2-run.sh`)  
must contain **only** the following changes relative to the original  
`zerorep-matrix-run.sh`:

1. Declare `readonly CARGO=/root/.cargo/bin/cargo` at the top of the script  
   (after the `set -euo pipefail` block).  
2. Before argument dispatch or any campaign-path side effect, verify:
   ```bash
   [[ -x "$CARGO" ]] || { echo "CARGO not executable"; exit 1; }
   CARGO_VERSION=$("$CARGO" --version)
   [[ "$CARGO_VERSION" == "cargo 1.96.1"* ]] || { echo "wrong cargo version: $CARGO_VERSION"; exit 1; }
   ```
3. Replace both executable bare `cargo` invocations with `"$CARGO"`, ensuring
   no executable bare `cargo` invocation remains.
4. Extend `--self-test` with a source-contract check that fails if any new
   lowercase `cargo` token appears anywhere in the script. The only two
   permitted occurrences are the `.cargo` directory and `cargo` executable in
   the exact declaration `readonly CARGO=/root/.cargo/bin/cargo`. Derive the
   program name from `${CARGO##*/}` so version checks, evidence filenames, and
   log messages introduce no additional lowercase token. This stricter
   whole-source invariant rejects every executable form, including `if cargo`,
   `! cargo`, `( cargo )`, `time cargo`, `command cargo`, and `env X=1 cargo`.
   The contract must also assert that the exact declaration line is present.
   It must additionally require exactly one copy of each complete preregistered
   suite command line using `"$CARGO" test --release` and
   `"$CARGO" test --release --test scheme_roundtrip`. Replacing either command
   position with `"$CARGO_PROGRAM"` must fail self-test even though it adds no
   lowercase source token.
5. Correct the inherited checkout-cleanliness helper so a failed `git status`
   is fatal; only a successful command with empty output is accepted as clean.
6. Before the Rust suite, verify the exact generation-1 root in §7: the five
   hashed files plus one real, empty `timing_logs/` directory. Reject missing,
   changed, additional, symlinked, or non-empty entries.

The source-contract check must be part of `--self-test`, for example:

   ```bash
   CARGO_PROGRAM=${CARGO##*/}
   [[ $(grep -oF "$CARGO_PROGRAM" "${BASH_SOURCE[0]}" | wc -l) == 2 ]]
   grep -Fxq "readonly CARGO=/root/.$CARGO_PROGRAM/bin/$CARGO_PROGRAM" \
     "${BASH_SOURCE[0]}"
   ```  
The self-test must run successfully with
`PATH=/usr/sbin:/usr/bin:/sbin:/bin`, proving the absolute Cargo path is
sufficient.

Items 5-6 are review-driven fail-closed admission corrections preregistered
after the first G2 review and before their implementation. They change no
scientific variable or measurement behavior.

The original runner file is preserved untouched in the generation‑1  
checkout and is never overwritten.

---

## 5. Admission gates (generation‑2)

All gates from §7 of the original preregistration apply to the generation‑2  
campaign. In addition, **before** any build or test step the runner must:

- Verify that `/root/.cargo/bin/cargo` is executable and reports `cargo 1.96.1`  
  (already covered by the runner’s own checks).  
- Confirm that the generation‑2 checkout path  
  `/root/cubr-levers/zerorep-matrix-g2-code` exists and its `origin/main` SHA  
  contains this amendment and the reviewed runner.  
- Assert that the generation‑2 output root  
  `/root/cubr-levers/zerorep-matrix-g2-20260809` does **not** exist.  
- Assert that the generation‑1 output root
  `/root/cubr-levers/zerorep-matrix-20260809` still exists and that all five
  preserved file hashes match §7.

The mandatory load‑average, CPU pin, unique‑process, binary‑hash, archive‑hash,  
and test‑suite gates remain exactly as specified in the original document.

---

## 6. Exact launch command

After this amendment and the corrected runner land on `origin/main` and  
undergo independent review, generate the generation‑2 candidate checkout:

```bash
git clone https://github.com/Arcanada-one/cubrim.git /root/cubr-levers/zerorep-matrix-g2-code
git -C /root/cubr-levers/zerorep-matrix-g2-code checkout --detach <resulting-main-sha>
```

Build the candidate binary, run the suite, and then launch once:

```bash
timeout 14400 systemd-run --wait --collect \
  --unit=cubr-zerorep-matrix-g2-20260809.service \
  --property=RuntimeMaxSec=7200 \
  /root/cubr-levers/zerorep-matrix-g2-code/documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809/zerorep-matrix-g2-run.sh
```

The unit must not be started before the review is complete, and it may be  
launched exactly once. No restart, no reuse of generation‑1 logs, no  
widening of timeout envelopes.

---

## 7. Preservation of generation‑1 artefacts

The output root `/root/cubr-levers/zerorep-matrix-20260809` is  
**immutable**. It must never be deleted, modified, or reused for any  
future campaign. Its journal entry documenting the `cargo` failure remains  
the single source of truth for the voided generation‑1 run.

The launch-time preservation manifest is:

```text
b6b96126eefa1a9b00581b1c7f2439ca5c605e1b8b4dceb14d4757a28c9fefbf  HASHES.tsv
012a973200c31c92f5447961e7915735a7ae0311f628d9f7a89c375fcc998615  cargo-test-release.log
7ffd8ea16586b73ca67e645fb79d68e6b83dd647b2068bdeb256e4708e4ae2d4  journal.log
544748ffc2ffbcd9218ff43f09b7292811d6ab00e1fad789105adfc5d31fd19f  results.tsv
7ae44fbaaaf4cf26cc68d1643cc49da562434914dbade295605aaf5972944cdf  roundtrips.tsv
```

The root also contains exactly one directory, `timing_logs/`, which is real
(not a symlink) and empty. Therefore the preserved root has exactly six
top-level entries: the five files above and that empty directory.

---

## 8. Reference documents

- Original preregistration:  
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809.md`  
- Original execution plan:  
  `documentation/ephemeral/plans/CUBR-ZEROREP-MATRIX-20260809-plan.md`  
- Generation‑1 runner:  
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809/zerorep-matrix-run.sh`  
- Generation‑2 runner (to be created):  
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809/zerorep-matrix-g2-run.sh`  
- This amendment:  
  `documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G2-20260809.md`

---

**No measurement result exists yet. The generation‑2 campaign must only be
launched after the amended runner has been independently reviewed and merged
into `origin/main`.**
