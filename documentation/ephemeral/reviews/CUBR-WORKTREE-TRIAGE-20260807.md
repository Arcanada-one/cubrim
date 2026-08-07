# Worktree triage — the "fourth one-disk incident" is a false alarm, verified chain by chain

**Date:** 2026-08-07. **Scope:** every unpushed commit chain in the cubrim
worktrees, triaged against `main` = `a5151b2`. **Headline:** none of the
flagged work is lost or unlanded — all of it reached `main` through squash
merges whose PR-side titles differ from the branch-side commit subjects,
which is exactly why both `git cherry` and message-matching sweeps missed
it. One additional unpushed chain the brief did not list was found and
triaged the same way. **Nothing needed pushing; every chain is discarded as
superseded, each with its proof below.**

## Verdicts

### 1. `reconcile/CUBR-0076-main` @ `545f890` (worktree `PR-10-salvage`) — SUPERSEDED by PR #19

The "table-driven decode sitting on one disk for six days" **landed on
`main` six days ago** as `56faebf` "perf: accelerate decoder table lookups
(#19)". Proof, in descending strength:

- The #19 squash body lists **all five** branch commits verbatim as bullets
  ("table-driven Huffman decode, and a data-loss bug it uncovered" /
  "in-process decode timing" / "remove the per-position allocation" /
  "table-driven decode for the order-2 context stage" /
  "reconcile(CUBR-0076): align salvage with current main") **plus six
  follow-ups the branch does not have**, including
  "fix(CUBR-0076): guard fast tables against invalid lengths".
- The order-2 fast table is live on `main` (`codec.rs:6380`
  `fast: Option<HuffTable>`, `codec.rs:6487` `build_bounded(&code_len,
  CTX_TABLE_BITS)`), as is `tests/scheme_roundtrip.rs` and
  `examples/decode_bench.rs`.
- The branch tree is **1,605 lines behind** current `main` (it predates the
  hostile-input hardening #26, the fuzz targets #28, the Kraft
  `checked_shl` guard, and the u16 fix #34); merging it now would be a
  regression, not a rescue.
- `git cherry` marks all five commits `+` (not equivalent) — that is the
  squash-merge artifact that fooled the sweep, not evidence of unlanded
  work.

The salvage's data-loss discovery also has a closed arc on `main`: its
round-trip suite became the CI "Lossless scheme round-trip" gate
(#19 + fixtures via #17), ran red, and was made green the honest way by
#34 (BWT schemes decline blocks past the v1 u16 primary-index ceiling,
consilium option c) — re-verified green 7/7 on 2026-08-06 during the
density slice.

### 2. `review/CUBR-0075-reconcile` @ `0c7179e` — SUPERSEDED (the brief did not list this one)

A **fourth** unpushed chain, found during this triage: the
pre-reconciliation lineage of the same salvage (same four subjects,
different SHAs) plus `c2b2333` "harden the decoder against hostile input".
`545f890` above was *created from it* as the align-with-main reconciliation
(deliberately dropping the hardening files that were landing separately),
and #19 squashed that. The hardening components each landed on their own
track: fail-closed decode + `limits.rs` + `tests/hostile_inputs.rs` via
#26 (`c3ca481`), fuzz targets via #28 (`eba22f1`). `main`'s versions of all
those files are strict supersets of this branch's.

### 3. `review/CUBR-0075-main-baseline-probe` @ `fb6b351` (worktree `PR-10-main-baseline`) — SUPERSEDED by the CI suite

One commit adding `tests/scheme_roundtrip_pr10_probe.rs`: a snapshot
instrument built to characterize then-`main` during the PR-10 review.
`main`'s committed `tests/scheme_roundtrip.rs` covers the same seven value
schemes over the same `payloads-v2` corpus under the same
`use_square_limit = false` configuration, as individually named, CI-gated
tests — green 7/7. The probe adds no coverage `main` lacks.

### 4. Detached `9821165` (worktree `PR-12-review`) — ALREADY IN THE LANDED RECORD via PR #12

The three-commit rar chain (pin `-mt16`; **mechanism correction: rar reads
`/sys/devices/system/cpu/online`, not the affinity mask**; second-host
confirmation). The `reproducibility/` tree at `9821165` is **byte-identical
to `main`'s** (`git diff origin/main 9821165 -- reproducibility/` is
empty). The #12 squash carried the whole chain: `main`'s
`reproducibility/README.md:83` has the strace `/sys` finding, the
per-host online-CPUs table records the second host, and `verify.py:26`
carries the corrected mechanism comment. **The brief's item 4 is therefore
already satisfied — the correction is reflected in the landed record, and
no update is needed.** (This worktree escaped the sweep for a different
reason than the others: detached HEAD, so there was no branch to sweep at
all.)

## The sweep lesson, so the fifth incident does not happen

Two distinct blind spots produced this scare: branches with **no remote at
all** escape "ahead of origin" sweeps, and **detached-HEAD** worktrees
escape branch enumeration entirely. Squash merges then defeat
message/cherry matching when checking whether content landed. The robust
sweep is one command per worktree, independent of branch state, followed by
a **tree-level** comparison for anything it surfaces:

```
git log --oneline origin/main..HEAD        # any commits main lacks?
git diff origin/main HEAD --stat -- <dir>  # does the TREE hold anything new?
```

`git cherry` and commit-subject matching are not evidence either way under
squash merges; the tree diff is.

## Follow-on for the next archival lever

`PR-10-salvage` is not a starting point — it is already the landed
foundation: `main` carries the fast Huffman tables, the order-2 context
fast path, and `examples/decode_bench.rs` (the A/B instrument that measures
the table against the retained scan baseline on one build). The next lever
per the adaptation verdict remains the `counter_state_lookup` layout attack
(measured ceiling ≤1.24× alone, ≤1.61× for the whole model on text) and/or
an update-scheme replacement (≤1.99×), with `decode_bench` and the 0075
profiler as the ready instruments.

No branch was pushed (nothing substantive to push); no merge was made; no
worktree was deleted (cleanup is now safe for all four, operator's call).
No DB writes; `evaluation` stays 0.
