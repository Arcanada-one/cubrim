# CUBR-NCI-MATCHCAP-20260811 — preregistration: CM2 match-model capacity/eviction on nci

**This document is committed to `main` BEFORE the probe is run.** It names the mechanism, derives the
ceiling from that mechanism (not from the measurement about to be taken), and states the predictions
that the measurement can refute. Ordering is the point: a ceiling computed after seeing the number is
not a ceiling.

## Why this lane

The density probe wave (`probes-20260809/INDEX.md`) closed six of seven named backends — NEW-02,
NEW-04, NEW-05, NEW-06, NEW-13 and H-25i are all NO-GO, and NEW-08 advanced to prereg and then
returned a preregistered NO-GO (#65). Its cross-lane finding #2 named the one surviving density
residual and the mechanism to aim at:

> The one sharp density residual is nci vs xz (+7.3%, ~105 KB), and it is a whole-file long-range
> effect on the CM2 rail … the next properly-framed hypothesis has a precise mechanism target: CM2
> match-model capacity/eviction on large highly-repetitive inputs.

No branch, PR or landed document owns that target. This lane takes it.

The decisive gap in the evidence: NEW-06 measured long-range coverage on **enwik8, webster and
samba** — and **not on nci**, the only file with a deficit. Its eviction survival table is also
generic, not nci-specific.

## Mechanism (from source, before any measurement)

CM2 carries three LZP-style match models m1/m2/m3 (`cm2.rs`):

- `M1_MIN=6`, `M2_MIN=3`, `M3_MIN=12` (cm2.rs:487-489)
- each is a **direct-mapped** table `vec![0u32; 1<<tbits]` storing the **absolute u32 position** of
  the last occurrence of the minlen-gram (cm2.rs:577); lookup follows it with **no distance window**
  (cm2.rs:570-575)
- `tbits_for = clamp(ceil(log2 len)+3, 18, 27)`, `TBITS_MAX = 27` (cm2.rs:441-460)

So the reach limit is not a window — it is **eviction**. A candidate at distance `d` survives roughly

    p_survive(d) = exp(-d / 2^tbits)

because each intervening position writes one pseudo-random slot per table.

**The load factor is the crux, and on nci it is favourable.** nci is 33,553,445 B
(sha256 `fc63a317…`), so `ceil(log2 len) = 25`, `tbits = 27`, giving **134,217,728 slots for
33,553,445 positions — 4× more slots than positions**. Consequences, computed from the model:

| distance d | survive @ tbits=27 | recoverable by ideal (no eviction) | recoverable by tbits 27→30 |
|---|---|---|---|
| 16 MiB | 0.8825 | 0.1175 | 0.1020 |
| 32 MiB | 0.7788 | 0.2212 | 0.1904 |
| 33.5 MiB (whole file) | 0.7697 | 0.2303 | 0.1981 |

Even the farthest possible candidate on nci survives at **77%**. Whatever the nci deficit is, at most
23% of far-distance candidates are lost to eviction.

## Ceiling, derived from mechanism

Baseline (meta-36, measured): cubrim nci `0.046335` = **1,554,699 B**; xz `0.043193` = 1,449,274 B.
Gap **105,425 B**, +7.3% relative, = **0.02514 bits/byte**. CM2's cost on nci is
`c = 8 × 0.046335 = 0.37068 b/B`.

Using NEW-06's per-covered-byte residual charge `f = 0.10 b/B` (its optimistic ideal), the margin an
ideal long-range layer can win per covered byte is only

    c - f = 0.27068 b/B

This is the crux of the ceiling and it is specific to nci: because CM2 already codes nci at 0.371
b/B, the margin is small in absolute terms. To close the xz gap the layer must recover

    0.02514 / 0.27068 = 9.29% of all bytes

and, since only the evicted fraction of far matches is recoverable, the **raw** coverage required at
>16 MiB nearest-previous distance is

- **42.0%** of bytes for a perfect, eviction-free match model, and
- **48.8%** of bytes for the concrete `TBITS_MAX` 27→30 lever.

For scale, the coverages NEW-06 measured at >16 MiB were **webster 1.469%**, **enwik8-head 0.957%**,
**samba 0.030%**. The requirement is 30–50× the largest figure ever measured on this corpus.

### A correction to the NEW-06 ceiling model, found while deriving this

`probe-new06-notes.md` states the model as

    bits/byte_new = (1-cov)*c + cov*f + H2(cov)

but its three published ceilings reproduce **exactly** without the `H2(cov)` term
(enwik8 0.18043, webster 0.12693, samba 0.14218 — each equal to `c - cov*(c-f)` to 5 decimals).
Applying the stated `H2(cov)` decoder-branch charge instead gives 0.23178 / 0.18584 / 0.16215 —
**every one worse than the measured baseline**, i.e. the layer never pays at all.

This does not change NEW-06's verdict; it strengthens it. But the stated model and the computed
numbers disagree, so anyone reusing that model gets inconsistent results. This lane therefore reports
**both bounds explicitly**:

- **optimistic (no flag charge)** — matches NEW-06's published arithmetic, `c - cov_rec*(c-f)`
- **decoder-branch-honest** — adds `H2(cov_rec)`, per Gotcha #6 as NEW-06 *stated* it

A real adaptive coder charges the flag at conditional, not marginal, entropy, so the truth lies
between. Both are reported; neither is silently chosen.

## Predictions (falsifiable, committed before the probe)

- **P1 — nci long-range coverage is far below the closing requirement.** Measured nci coverage at
  >16 MiB nearest-previous distance will be **< 10%** of sampled anchors, against the 42.0% needed.
  *Refuted if* it is ≥ 42.0%, which would make the capacity lever a GO and this ceiling wrong.
- **P2 — the eviction-honest incremental ceiling closes under a fifth of the gap.** The `TBITS_MAX`
  27→30 lever will recover **< 20%** of the 105,425 B deficit on the optimistic bound.
  *Refuted if* it recovers ≥ 20%.
- **P3 — nci is more long-range-repetitive than the text files.** nci coverage at >16 MiB will
  exceed webster's 1.469%. This one is expected to be *right* while P1 and P2 still hold: nci can be
  unusually repetitive and the lever still not pay, because the binding constraint is the 0.27068
  b/B margin, not the repetition. *Refuted if* nci coverage ≤ 1.469%.

P3 is stated separately on purpose. If P3 holds and P1 holds, the finding is that **repetition is not
the constraint — CM2's already-low cost on nci is**, and no capacity lever can be justified by
long-range repetition alone.

## Method (fixed before running)

Reuse the landed, unmodified `probes-20260809/probe_longrange.py`: 16-byte grams, numpy rolling
64-bit hash, content-based sampling `(h & 15) == 0` so every occurrence of a sampled gram is indexed
and the nearest previous occurrence is exact for sampled grams; raw 16-byte verification kills
64-bit collisions; buckets of nearest-previous distance ≤64K, 64K-1M, 1-8M, 8-16M, >16M.

Input: **whole** nci, 33,553,445 B, sha256 `fc63a31770947b8c2062d3b19ca94c00485a232bb91b502021948fee983e1635`
— not a head slice. (NEW-06 had to use a 32 MB head sample for enwik8; nci fits whole, so the
whole-file effect the residual lives in is actually observable here.)

Gates: report the sample fraction and collisions-dropped, as NEW-06 did. Per-file figures only — no
corpus aggregate, no corpus-wide average. This probe touches no encoder, no wire format, and writes
nothing to the database.

## What a NO-GO here would mean

If P1 and P2 hold, the last named density residual is closed on mechanism: the nci gap is not
recoverable by match-table capacity, and the density branch's named backlog is exhausted rather than
merely unexplored. That is a finding, not an absence of one — and it should redirect effort to the
speed branch, where cubrim is last of ten by 15×.
