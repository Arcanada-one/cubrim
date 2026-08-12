# CUBR-0096 — inner sticky value-stream selection: gate result

**Verdict: implemented, measured, and KILLED by its pre-registered gate.**
Measured 2026-08-02. Landed here 2026-08-12 by the CUBRIM-PROGRAM lane.

> **Read this before writing any sticky-selection code.** The lever described in
> `documentation/ephemeral/plans/CUBR-0096-sticky-selection-design.md` was built in full and
> measured on 2026-08-02 under the then-current label `CUBR-0092`. It failed its gate. For ten
> days that result existed only in an uncommitted worktree, so `origin/main` showed no
> `vs_pin` / `vs_sticky` / `VsSticky` and the lever read as unbuilt. It was not unbuilt — it was
> unrecorded. § *Why this document exists* covers how that happened.

## The gate, and what it returned

Pre-registered, all four required:

| # | Requirement | Result |
|---|---|---|
| 1 | ≥ 1.50× end-to-end encode speedup on one representative image **and** one independent executable | **FAIL** — 1.33× and 1.05× |
| 2 | Byte-exact round-trip on every measured configuration | PASS |
| 3 | No target-file output growth above 1% | PASS — growth was exactly zero |
| 4 | ≤ +0.50% relative ratio cost on the 24-file corpus | **not established** — see § *What was never measured* |

Requirement 1 is the one that fired. Requirements 2 and 3 passing is what makes the result
interesting rather than merely negative: the mechanism was *correct*, it simply did not buy
enough speed to be worth a ratio-costing preset.

## Measurement

Same host and harness for both arms. `dev-ai`, CPUs `0-15`, `CUBR_THREADS=16`. These are
internally comparable baseline-versus-candidate timings on `dev-ai` (64 cores, pinned 0-15) and
**must not be compared with any N=24 campaign figure** — the campaign stand is a different,
16-core machine.

- baseline binary `sha256:d2ee91bf8b2eec3c144183ebde06fb4e72bae5c89a96d23be8bd1e08fd60dd19`
- candidate binary `sha256:a9fec5a2a1c74d2337581afc28eae52a0225ee5d590033bdf8100a9191e27374`

| Representative | Baseline encode | Candidate encode | Speedup | Compressed bytes (base / cand) | Round-trip |
|---|---:|---:|---:|---|---|
| x-ray | 131.10 s | 98.67 s | **1.33×** | 3,637,036 / 3,637,036 | PASS |
| ooffice | 222.34 s | 211.61 s | **1.05×** | 1,763,460 / 1,763,460 | PASS |

Compressed bytes are **identical** on both files, so on these two representatives the schedule
never re-pinned into a worse choice — consistent with F18's finding that the competition
computes a constant where it runs.

### Statistical honesty about the executable cell

The ooffice candidate cell is n=2, not n=1. An earlier encode produced 217.44 s (artifacts born
18:07:10 +0200) before a later encode overwrote the `.time` and output files at 18:12:11 +0200
with the authoritative 211.61 s. The two candidate runs span **5.83 s**, while the entire
baseline-to-selected difference is **10.73 s**. The 1.05× executable result is therefore *not
distinguishable from noise* at n=2 versus n=1. The x-ray comparison is n=1 on each side: its
1.33× is a single-run comparison, not a repeatability estimate.

The original `representative.tsv` had a corrupted `enc_rss_kib` column and was renamed to
`representative.raw.tsv`; the canonical TSV was regenerated from the `.time` files.

### RSS

Encode peak RSS moved in **opposite directions** on the two representatives: x-ray 1,746,428 KiB
→ 1,542,056 KiB (−11.70%), ooffice 6,662,864 KiB → 7,340,856 KiB (+10.18%). One pinned run per
representative cannot distinguish noise from retained candidate state. **No memory benefit is
claimed**, and the cause is unresolved.

## The candidate implementation

Rescued to branch `rescue/INFRA-0394/codex/cubr-0092-inner-sticky` at commit `cfea5da8`
(+564/−155 in `code/cubrim-rs/src/codec.rs`). It is the design document's § Mechanism, built:

- `StickyValueStreamPlan { compete_blocks, recheck_every }` and
  `enum BaseValuePolicy { Full, Pinned(ValueScheme), Sticky(plan) }`
- `encode_rans_family_value_stream_pinned` — the run-only-this-scheme primitive the design
  identified as missing
- `encode_blocks_parallel_sticky` + `sticky_probe_indices` — probe set is
  `{ i < compete_blocks } ∪ { compete_blocks + k·recheck_every }`, a pure function of block index
- `const MED16_STICKY_PLAN = { compete_blocks: 8, recheck_every: 16 }`, deliberately scoped to
  MED16 as the only authorized caller so the default encoder stays byte-identical

## The part that matters most: schedule tuning cannot rescue this

`MED16_STICKY_PLAN` probes 8 blocks then every 16th. That is `8 + ⌈(N−8)/16⌉` probes — **8.33% of
blocks at N=384, tending to 6.25% as N grows.** The remaining ~92% were already pinned, so almost
all of the available saving had already been taken.

Bound the best case. A *perfect oracle* — one that knows the winning scheme with no probing at
all — can only remove the residual probe cost. Deriving that from the measured numbers alone:

```
saving_measured = baseline − candidate
probe_cost      ≤ saving_measured / (1 − probe_fraction) × probe_fraction
oracle_time     ≥ candidate − probe_cost
```

| Representative | probe fraction | saving | residual probe cost ≤ | oracle time ≥ | **oracle speedup ≤** |
|---|---:|---:|---:|---:|---:|
| x-ray | 6.25% | 32.43 s | 2.16 s | 96.51 s | **1.358×** |
| x-ray | 8.33% | 32.43 s | 2.95 s | 95.72 s | **1.370×** |
| ooffice | 6.25% | 10.73 s | 0.72 s | 210.89 s | **1.054×** |
| ooffice | 8.33% | 10.73 s | 0.98 s | 210.63 s | **1.056×** |

**The ceiling is ~1.37× on the image and ~1.06× on the executable, against a 1.50× gate.** No
choice of `compete_blocks` / `recheck_every`, and no smarter re-check heuristic, can clear the
bar — a perfect oracle does not clear it either. The gate is not failing because the schedule
was badly tuned; it is failing because the value-stream competition is a smaller share of
whole-file encode time than the 2 MB slice in F18 implied. Amdahl, not tuning.

This derivation is **arithmetic over the measured cells plus the probe schedule read from the
candidate source** — it introduces no slice figure. Its two assumptions, stated so they can be
attacked: per-block competition cost is roughly uniform across blocks, and pinning removes
essentially all of a non-probe block's loser cost. If either is badly wrong the bound moves, but
both would have to be wrong by a wide margin to reach 1.50×.

**What this does not refute:** attacking the same waste by a *different* mechanism. The bound
above prices the sticky-selection lever specifically. A change that makes the winning candidate
itself cheaper, or that removes losers without probing at all (a cheap static predictor from
block statistics, say), is not covered by this arithmetic and would need its own measurement.

## What was never measured

Stated plainly so nothing here is read as broader than it is:

- **The corpus arm never ran.** The 24-file sweep was stopped after 12 baseline rows and before
  any candidate row. Requirement 4 is not established either way. **No corpus verdict is claimed
  and no statement is made about the remaining corpus files.**
- Only two representatives were measured. Nothing is claimed for text or database — and per F18
  the mechanism cannot even be observed there, since L1 abandons the deferred base before any
  block completes.
- Nothing has been run at enwik8 scale.

## Shipping boundary

The candidate source was never merged and is not proposed for merging. No PR, no deploy, no
production claim. **`--max` remains byte-identical to v0.3.2**; the shipped encoder never
contained this code.

## Evidence

- `dev-ai:/root/cubr0092-inner-sticky-20260802T155722Z` — `representative.tsv`,
  `representative.raw.tsv`, `binary-sha256.txt`, `logs/`, `corpus/` (the 12 partial baseline rows).
- `arcanada_cubrim.hypotheses` row `NEW-29`: `status=closed`, `measured=t`,
  `measure_task=CUBR-0092`, verdict `KILLED by pre-registered gate`. Extended, not duplicated.
- Candidate source: `rescue/INFRA-0394/codex/cubr-0092-inner-sticky` @ `cfea5da8`.

Re-verified 2026-08-12 by the CUBRIM-PROGRAM lane rather than taken on trust: the evidence
directory exists and its `representative.tsv` matches every cell quoted above, and the `NEW-29`
row reads as described.

## Why this document exists

The result was produced on 2026-08-02 and left in an uncommitted worktree. `INFRA-0394` rescued
the working tree to a branch on 2026-08-11 — nine days later, and only as part of a general
sweep rather than because anyone was looking for this. On 2026-08-12 a second lane, reading
`origin/main` correctly and finding no `vs_pin` / `vs_sticky` / `VsSticky`, concluded the
mechanism was unbuilt and began re-implementing it from the instrumentation step.

Both lanes were reading their sources correctly. The failure is that a finished, gate-firing
negative result was never written anywhere a reader would look, and *absence from `main` was
indistinguishable from never-attempted*. A negative result that is not recorded gets paid for
twice.

## Related

- `documentation/ephemeral/plans/CUBR-0096-sticky-selection-design.md` — the design this
  implements, and its live-lane status note.
- FINDINGS F17 / F18 — the evidence base: the eight-way per-block competition, and its
  `FINAL:` counter showing geomix winning 384/384 blocks on both x-ray and ooffice.
- F19 — why per-class corpus measurement is mandatory and slice figures are forbidden.
