# NEW-02 evidence reconciliation, 2026-08-11

Two separate NEW-02 records now exist on `origin/main`, and they have been read
as if they were in tension. They are not. This note reconciles them against
live main, states what is authenticated, and names the one defect that blocks
the historical-validation lane.

Reconciled against `origin/main` `b9dfb4d26c01bdf3852713b64c400c6b67efd4a8`.

## The two records are about different questions

| Record | Question | Disposition |
|---|---|---|
| `probes-20260809/probe-new02-notes.md` (PR #85) | Should Cubrim build its own PPMd var.H/I backend for text? | **NO-GO** |
| `CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md` + its raw campaign | How do PPMd order and memory affect charged archive bytes per file? | **CHARACTERIZED_NO_SELECT** |

The probe closed a *build* hypothesis: the parity milestone it was aiming at
was already overshot by the shipped CM2 on all 11 registered text files and on
`osdb`, and the hypothesis's own optimistic ceiling (`ppmd × 0.97`) is dominated
by current cubrim on 10 of 12 files. The oracle grid is a *characterization* of
an external tool's parameter surface; it preregistered no ceiling, no
aggregate, no winner rule, and issued no selection.

A NO-GO on building the backend does not invalidate a characterization that
never proposed building one. Both stand. Neither authorizes a source change,
and no product selection exists on either path.

The registry already agrees. Read read-only on 2026-08-11, the single `NEW-02`
row is `status=closed`, `measured=f`, with empty `measure_date`/`measure_task`
and 0 measurement rows; its `updated_at` is `2026-08-11 12:34:47+00`, the
moment PR #85 merged. So the row was closed by the backend NO-GO, and the empty
measurement fields correctly reflect that the oracle grid is a characterization
whose numbers live in the evidence package, not in the database.

That closure applies to the *hypothesis*. The historical-validation work below
is not a hypothesis and does not reopen one: it is verification of an already
captured evidence package, and it can proceed against a closed row without
contradicting it.

**The historical NEW-02 raw campaign must never be rerun.** Nothing in this
note is authority to re-execute it.

## What is authenticated, measured today

Every frozen NEW-02 identity in
`datarim/plans/NEW-02-historical-result-validation-plan.md` still holds on live
main after main advanced:

| Identity | Plan value | State on `b9dfb4d` |
|---|---|---|
| Preregistration blob | `d96df7e3478a6ba52b737ef30dea63d68b0e01ac` | unchanged |
| Harness blob | `3acaa4a5fc2b5622404f041a28575cbf9ad10bd5` | unchanged |
| Harness-test blob | `ccf6613b13aa178eb1bb6a0896e5ea8b0276e10b` | unchanged |
| Execution commit `708cda945a285526610371d812e4f54725eb6baf` | — | present, ancestor of main |

The immutable raw publication was re-authenticated end to end on 2026-08-11:

```
COMPLETE.manifest_sha256  4a39fb5ec1914ae7e1e296c44b2cec4cf4ecf2afa48af3216a9ec2552f3cb88c
recomputed MANIFEST.json  4a39fb5ec1914ae7e1e296c44b2cec4cf4ecf2afa48af3216a9ec2552f3cb88c
manifest entries          974
files hash-checked        974
missing files             0
hash / size mismatches    0
observation cells         243
```

The tree is mode `0444`/`0555` throughout. The capture survived main advancing
intact: **the raw bytes are not the problem.**

## The one defect that blocks the lane

The derived result package exists and is substantively complete — 243/243 PASS
on round-trip, `cmp`, SHA-256, and every return code, verdict
`CHARACTERIZED_NO_SELECT` / `NO-SELECT` / `NOT_ISSUED` — but its verifier
cannot pass today:

```
NEW02_RESULT_VERIFICATION=FAIL reason=landed raw-publication validation failed:
code identity is not the actual exact origin/main SHA
```

The cause is not drift in any NEW-02 artefact. `verify_new02_results.py` loads
the landed capture harness and calls its `validate_publication`, and that
harness guards (`new02_oracle_grid.py:393-396`):

```python
if (_git_output(repo_root, "rev-parse", "HEAD") != code_sha
    or _git_output(repo_root, "rev-parse", "origin/main") != code_sha):
    raise HarnessError("code identity is not the actual exact origin/main SHA")
```

That predicate is **correct at capture time** — it stops a campaign running on
anything but exact main. It is **wrong at validation time**, because it binds
authentication to a moving branch ref. The execution commit `708cda9` is now
many commits behind `b9dfb4d`, so the check can never pass again, and it will
fail harder every time main advances. Its own test suite shows the defect is
isolated: **8 of 9 tests pass**; the single error is this check.

This is the same class as the NEW-24 G6 prebuild failure — an identity bound to
a mutable external input rather than to the frozen artefact. It is recorded as
gotcha 12 in `CLAUDE.md`.

The repair is already specified: the historical-validation plan's Task 5
replaces the derived builder's mutable-harness dependency with a standalone
version-frozen validator. This note changes no code and performs no repair; it
records that the plan's premise is confirmed by live measurement rather than by
assumption.

## Work at risk

The derived package is **untracked in a worktree and has never been committed
to any branch**, so it is invisible to `git status` sweeps that only inspect
tracked files and to every branch-based sweep. Its exact bytes, as of
2026-08-11 at `/home/dev/.worktrees/cubrim/CUBR-NEW02-RESULT-PACKAGE/documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/`:

```
529ff0b05eba3155c4a37a0208aaa37cd5c42ce19e9fd37398351595201c6ee0  effects.tsv
1d3fef5e8dd141939e9e4b94dc9ea13ef73b9840332ec4c2fea618d749530a80  provenance.json
740c749f53f552239c1f14e77f19c4dfd7c68b8fd7c857131ca42ae84b200240  README.md
c9489a378b9e0a246ca3c594b85146e8d57e970214c105e331b7273b8a420c8f  results.tsv
834eff234962250268f72fa8cd274db08b7a2e2453ad649c50e8602151e1165d  SHA256SUMS
326aeec7d27ff73f6559d87ac6fe96db4712b4a516f9d44a9aa8ca565e341116  summary.json
8af37cd0826d54c6f3a9e63becb7c4d8e61aca9dd139d3efde5b561490e72b45  test_verify_new02_results.py
8be1b346318b2454c5c91c47dec4b5b9da0b35cc611b36c3923412f468c90aec  verify_new02_results.py
```

It is deliberately **not landed here**: its verifier is RED, and the plan
specifies modifications to six of these files before they reach main. Landing a
package whose own verifier fails would put an unverifiable result on main.
Recording the hashes makes the work recoverable and makes any silent loss or
alteration detectable.

## Disposition

- The two NEW-02 records are consistent; no reconciliation edit is required to
  either.
- The raw publication is authentic and immutable as of 2026-08-11.
- The historical-validation lane remains **open and actionable**, blocked on
  exactly one specified defect, not on evidence integrity.
- No database, API, site, social, credential, or selection mutation. The
  `NEW-24` and `NEW-02` registry rows were read read-only and not written.
