# NEW-24 full-binary G6: terminal NO-ATTEMPT before any build

**Verdict: `NO-ATTEMPT / NO-SELECT`. Route reached: prebuild-only.**

G6 terminated at the first of its four one-shot transitions. The prebuild
allowance is consumed; validation, admission, and campaign were never reached
and their allowances are unspent. No binary was built, no measurement was
taken, no source change is selected, and no database, API, site, social, or
credential state was touched.

## What the prebuild proved before it stopped

The failure is narrow and the surrounding machinery worked. Both independent
source clones detached cleanly at the frozen source commit
`830a9a31deb00926a97f3fa5bd74f58003573fc0`, and each independently generated a
`Cargo.lock` that was **byte-identical to the other** —
`0d17c1fc2ac4e17ef3c9a0ca0c21468950c820607ea0ce11875f9698d688d924`, 41115
bytes, from two separate Git object stores. The double-source-tree independence
property the prebuild exists to establish held exactly as designed.

What failed is the comparison against the preregistered constant:

```
expected  0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9
observed  0d17c1fc2ac4e17ef3c9a0ca0c21468950c820607ea0ce11875f9698d688d924
```

`assert_lock_identity` rejected the tree and the helper exited 1 with its
terminal marker. Per the plan's Task 5 failure branch, every owned path was
preserved read-only, Tasks 6–8 were skipped, and this package is Task 9.

## Mechanism: the frozen lock identity was unreproducible by construction

This is not host drift, a transport fault, or a flake. It is a structural
defect in the protocol, and it was measured rather than inferred:

1. `code/cubrim-rs/Cargo.lock` is **gitignored** — it is never committed, so
   there is no pinned lock in the repository to restore.
2. Every dependency in `code/cubrim-rs/Cargo.toml` is a **semver-compatible
   range** (`aes-gcm = "0.10"`, `rand = "0.8"`, `ureq = "2"`, and so on), not
   an exact pin.
3. The protocol regenerates the lock with `cargo generate-lockfile`, which
   resolves to the latest compatible versions **against the live crates.io
   index at the moment it runs**. The console log records
   `Locking 174 packages to latest compatible versions`.
4. The frozen `LOCK_SHA` constant was captured on **2026-08-09T16:57:54Z**.

So the constant pins a *derived* artifact while its input is *externally
mutable*. It was guaranteed to break as soon as any one of 174 packages
published a semver-compatible release. It survived G2 through G4 only because
those ran within hours of the capture.

The specific cause is identified, not assumed. Three crates in the resolved
set were published **after** the frozen-lock timestamp and **before** the G6
prebuild ran:

| crate | version | published (UTC) |
|---|---|---|
| `futures-core` | 0.3.34 | 2026-08-11T12:13:01.547638Z |
| `futures-task` | 0.3.34 | 2026-08-11T12:13:07.886026Z |
| `futures-util` | 0.3.34 | 2026-08-11T12:13:19.272525Z |

All three appear at exactly those versions in the retained lock, which is
included in this package as evidence and re-checked by the verifier. They were
published roughly one hour before the prebuild executed. A run started on
2026-08-10 would have passed; this one could not.

## Zero-effect proof

| Quantity | Count |
|---|---:|
| Release binaries built | 0 |
| Prebuild receipts published | 0 |
| Admission services submitted | 0 |
| Campaign services submitted | 0 |
| Campaign cells | 0 |
| `perf.data` / stat / record artifacts | 0 |
| Attribution / timing artifacts | 0 |
| Database / API / site / social / credential mutations | 0 |

`cubr-new24-full-binary-g6-admission-20260811.service` and
`cubr-new24-full-binary-g6-20260811.service` were `LoadState=not-found` both
immediately before and immediately after the prebuild. No systemd unit was ever
created under G6, so `unit-properties.txt` and
`systemd-journal.canonical.jsonl` each carry an explicit `[NOT REACHED: …]`
record. That absence is recorded as absence — never as `N/A`, never as `PASS`.

`target-a`, `target-b`, the receipt root, the receipt `.partial`, the map
dry-run root, the campaign root, and the admission-inputs `.env` were never
created. Only `src-a` and `src-b` exist, both preserved at mode `500`.

## No selection, and no statistical claim

G6 produced no sample on any file, so P1–P5 are not evaluable and the per-file
evaluation is **empty rather than fabricated**. No source change is selected.
The G5 evidence is unchanged: its retained incident-manifest blob
`49fb705f5230a35e43726d4f6a333e47c5cb1b29` and canonical-journal blob
`5ea61262dacd442fdf1676a7a7613c8e5534b6a3` were reauthenticated on the exact
instrument main before the prebuild ran and were not written to.

## What this costs and what it does not

G6 cannot be retried. Its prebuild allowance is spent, and a failure never
authorizes a second invocation under the same protocol. The full-binary
attribution question NEW-24 was built to answer therefore remains open, and any
future attempt is a **new protocol** with a new preregistration — not a G6
retry and not a reinterpretation of this record.

The instrument itself is not implicated. All eight instrument files are on
`origin/main` at `756ff160814cb1a8b452df68ad844514e8cf54a6` with exact-head CI
success, and all four suites passed both locally and from the materialized
remote checkout before the prebuild ran. The defect is in a preregistered
*constant*, not in the code that checks it — and the check working correctly is
why this is a clean `NO-ATTEMPT` rather than a silently mismatched build.

## The lesson worth keeping

**A frozen identity must pin its inputs, not its outputs.** Pinning a
`Cargo.lock` hash while regenerating that lock from unpinned semver ranges
against a live registry is a time bomb: it holds only until any transitive
dependency publishes a compatible release, and it fails in a way that consumes
a one-shot allowance. Any successor protocol must either commit the exact
`Cargo.lock` as a reviewed artifact and build with `--locked`, or vendor the
registry state — so that the build inputs are fixed by the repository rather
than by the wall clock.

## Verification

`verify_result.py` is fail-closed over every predicate in this record:
identity, terminal state, zero-sample and zero-admission counts, mapping,
conservation, statistics, publication, and no-selection. It recomputes each
evidence hash from the files on disk rather than trusting the declared values,
and it re-derives the observed lock SHA from the retained lock bytes.

`test_verify_result.py` runs 60 mutations in fresh processes: 0 no-op mutants,
0 surviving mutants, plus a delete-prove-RED / restore-prove-GREEN cycle.
