# CUBR-0075 — triage of the unmerged profile branches

**Date:** 2026-08-11 UTC
**Verdict:** land the evidence, discard the instrumentation, retire both branches.

## Why this exists

Two CUBR-0075 branches have sat on the remote without a PR:

| branch | ahead of main | contents |
|---|---|---|
| `codex/cubr-0075-profile` | 21 commits | decode-attribution evidence + profiling instrumentation |
| `CUBR-0075-speed-streaming-core` | 1 commit | a codec-level probe, on a base predating PR #19 |

That mattered because **documents already merged into `main` cite evidence that
lived only on an unmerged branch.** `CUBR-0076-GEOCM-CEILING-20260806.md` and
the CUBR-0076 prototype-shape document quote the deep attribution's numbers and
say, in as many words, "still unmerged/no PR — evidence pushed to remote". A
published conclusion whose evidence is one `git push --delete` away from
vanishing is a provenance hole, not a filing inconvenience.

## What was checked

- **Merge status.** Neither branch is an ancestor of `main`; neither has landed
  by content.
- **Split of the diff.** `codex/cubr-0075-profile` changes 33 files: 13 under
  `documentation/` (the evidence), 12 under `code/` and 8 under
  `bench/web-benchmark/` (the instrumentation that produced it).
- **Instrumentation status.** `code/cubrim-rs/src/prof.rs` with `CUBRIM_PROFILE=1`
  is **already on `main`**, landed via PR #19 and its follow-ups. The branch's
  own instrumentation touches `codec.rs`, `cm2.rs`, `bitpack.rs` and
  `distance_map.rs` at a base six weeks behind a `main` where `codec.rs` alone
  has since been rewritten repeatedly and `cm2.rs` changed today. Merging it
  would be a large conflict resolved in favour of stale code — the same shape as
  the CUBR-0074 branch triage, which reached the same conclusion.
- **Evidence consistency.** The markdown write-ups carry exactly the figures
  the landed documents quote: whole-model Amdahl ceiling **22.5x**, best single
  split **2.09x**, and the "Dependency 13" retrofit negative — range-coder
  primitives at **2.0185%** of substage cycles, capping a retrofit at
  **1.0206x**. The citations resolve against this evidence, so landing it makes
  the published chain complete rather than adding a second account of it.

## Decision

1. **Land the 13 documentation files** onto current `main` from a fresh branch —
   evidence, write-ups and the two plans, ~12 MB dominated by three raw
   attribution JSONs. Consistent with how this repository already stores
   research evidence (`raw/` directories carrying `perf.data`, `.cub` archives
   and profiler dumps).
2. **Discard the instrumentation**, superseded by `prof.rs` on `main`. Nothing
   is lost that `main` cannot already do: `CUBRIM_PROFILE=1` produces the
   candidate-attribution table this branch's patches existed to produce.
3. **Discard `CUBR-0075-speed-streaming-core`.** Its single commit adds a probe
   on a pre-PR-#19 base; the decode-timing capability it was reaching for landed
   in-process long ago, and the CUBR-0076 work has since measured the same axis
   end to end on a quiet host.
4. **Retire both remote branches** once this lands, so the next reader is not
   triaging them a third time.

## What is deliberately not claimed

This lands **evidence**, not new measurement. No number in the attribution
files is re-derived, re-run or re-interpreted here, and no verdict elsewhere
changes because of it. The CUBR-0075 hypotheses themselves — speed and
streaming — remain open and unaddressed by this triage; the streaming API in
particular is still unbuilt and is the task's live work.
