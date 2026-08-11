# CUBR-NCI-MATCHCAP-20260811 — results: CM2 match-model capacity/eviction on nci

**VERDICT: NO-GO**, by a factor of 552 on the headline requirement, robust to every correction
tried. One of the three preregistered predictions is **refuted** — and the refutation is the
substantive finding.

Preregistration: `CUBR-NCI-MATCHCAP-20260811.md`, committed to `main` as `38b939e3` at
**2026-08-11T16:47:37Z**. Probe ran **16:48:10Z–16:48:28Z**. The prediction was on `main` before the
measurement existed; that ordering is the evidence.

## Measurement

Whole nci — 33,553,445 B, sha256 `fc63a317…`, not a head slice — through the landed, unmodified
`probe_longrange.py` (sha256 `c1bcb89a…`). 8,764,893 sampled anchors, **0 hash collisions dropped**,
1.88% with no previous occurrence.

| nearest-prev distance | coverage | mean-ext-len |
|---|---|---|
| ≤64K | **95.028%** | 29.5 |
| 64K–1M | 2.072% | 68.0 |
| 1M–8M | 0.789% | 87.4 |
| 8M–16M | 0.156% | 142.3 |
| >16M | **0.076%** | 81.2 |

Cumulative: >1M **1.020%**, >8M **0.231%**, >16M **0.076%**.

Sample fraction is 26.12%, well above NEW-06's 6.28% (enwik8) / 5.99% (webster) / 12.69% (samba).
Stated honestly, as NEW-06 did for samba: content-based `(h & 15) == 0` sampling is unbiased over the
gram *population*, but nci's heavily repeated grams skew hash-mod density, so more positions qualify.
This inflates the sample, not the coverage ratios.

## Predictions, scored

| | prediction | threshold | measured | verdict |
|---|---|---|---|---|
| **P1** | nci coverage >16 MiB < 10% | refute at ≥42.0% | 0.076% | **HOLDS** |
| **P2** | `TBITS_MAX` 27→30 recovers <20% of the deficit | refute at ≥20% | 0.44% | **HOLDS** |
| **P3** | nci coverage >16 MiB exceeds webster's 1.469% | refute at ≤ | 0.076% | **REFUTED** |

## P3 refuted: nci is not long-range repetitive — it is intensely *local*

The prereg expected nci, as the ultra-repetitive file, to show *more* long-range structure than the
text files. It shows **19× less** than webster (0.076% vs 1.469%) and less than enwik8-head (0.957%).
**95.028% of nci's nearest-previous occurrences are within 64 KB.**

That inverts the premise the lane was built on. The probe wave's cross-lane finding #2 recorded that
the nci deficit "is a whole-file long-range effect on the CM2 rail", inferred from cubrim beating xz
on a 4 MB slice (0.0481 vs 0.0610) and losing only at 33.5 MB. The scale-dependence is real and
measured; **the long-range-match explanation of it is not supported by nci's actual structure.**
There is almost nothing out there at long range for a match model — capacity or otherwise — to find.

Whatever makes cubrim lose ground on nci between 4 MB and 33.5 MB, it is not repeats beyond the
match tables' effective reach. That correction is worth more than the NO-GO: it removes the one
mechanism the density branch still had a name for, and it does so from measurement rather than
argument.

## Ceiling vs measurement

Mechanism (preregistered): m1/m2/m3 are direct-mapped `1<<tbits` tables of absolute u32 positions
with no distance window, so reach is bounded by eviction, `p_survive(d) = exp(-d/2^tbits)`. On nci
`tbits = 27` gives 134,217,728 slots for 33,553,445 positions — **4.00× more slots than positions** —
so even the farthest possible candidate survives at 77%.

CM2 already codes nci at `c = 0.37068 b/B`. Against NEW-06's `f = 0.10`, the margin per covered byte
is `0.27068 b/B`. Closing the 105,425 B gap needs 9.29% of all bytes recovered — **42.0% raw coverage
at whole-file distance**. Measured: 0.076%.

| lever | recoverable coverage | optimistic | branch-honest |
|---|---|---|---|
| ideal (eviction-free) | 0.0470% | +533 B (**+0.51%** of gap) | −24,092 B |
| `TBITS_MAX` 27→30 | 0.0409% | +464 B (**+0.44%** of gap) | −21,318 B |

Both bounds are reported because the NEW-06 notes state a decoder-branch charge their published
numbers omit (see below). Even the optimistic bound — which charges the flag channel nothing —
recovers **half a percent** of the deficit. Raising `TBITS_MAX` on nci would buy roughly **464
bytes**.

### Robustness

The probe's coverage proxy is anchor-fraction, and the far buckets extend 3–5× longer than the ≤64K
bucket, so anchor-fraction under-states their byte coverage. Correcting for it does not change the
verdict:

| correction | recoverable | optimistic | branch-honest |
|---|---|---|---|
| raw anchor-fraction | 0.0470% | +533 B (+0.51%) | −24,092 B |
| ext-len weighted | 0.1581% | +1,795 B (+1.70%) | −69,481 B |
| ext-len weighted ×2 (pessimistic) | 0.3163% | +3,591 B (+3.41%) | −125,681 B |

Worst case tried, the lever recovers 3.41% of the gap and is strongly negative once the flag channel
is charged at all. The NO-GO does not depend on the proxy.

## Correction of record: the NEW-06 ceiling model

`probes-20260809/probe-new06-notes.md` states

    bits/byte_new = (1-cov)*c + cov*f + H2(cov)

but its three published ceilings reproduce **exactly** without the `H2(cov)` term — 0.18043 /
0.12693 / 0.14218 equal `c - cov*(c-f)` to five decimals. Applying the stated decoder-branch charge
instead yields 0.23178 / 0.18584 / 0.16215, **every one worse than its own measured baseline**, i.e.
the layer would never pay at all.

NEW-06's NO-GO is unaffected and in fact strengthened. But the stated model and its arithmetic
disagree, so any lane reusing that model gets inconsistent numbers. Both bounds are reported here and
in `ceiling.py`; neither is silently chosen. A real adaptive coder charges the flag at conditional
rather than marginal entropy, so the truth lies between the two.

## Scope

This covers nci only, measured whole. It is a structural measurement of the input, not of the
encoder: no encoder, wire format, `decode()`, preset, counter or database was touched, and no
hypothesis row was written. Per-file figures only — no corpus aggregate, no corpus-wide average.
Wall-clock is not reported because nothing here is a speed measurement.

Not measured, stated as a void: **what does explain nci's 4 MB → 33.5 MB scale-dependence.** This
lane refutes the long-range-match explanation but does not supply the replacement. Candidates worth a
properly framed hypothesis — CM2 context dilution or mixer adaptation at scale, or xz's parse
behaviour on locally-periodic data — are unmeasured and must not be reported as findings.

## Reproducing

```
cd documentation/ephemeral/research/CUBR-NCI-MATCHCAP-RESULTS-20260811
python3 ceiling.py        # regenerates every table above from nci-probe.out
```

`ceiling.py` parses the raw probe output; no figure in this document is hand-typed arithmetic.
Re-running the probe itself needs the corpus file named in `provenance.txt` (sha256 recorded).

## Consequence for the epic

The density branch's named backlog is now exhausted rather than unexplored: NEW-02, NEW-04, NEW-05,
NEW-06, NEW-08, NEW-13 and H-25i all returned NO-GO, and the one residual they left with a named
mechanism is closed here — with its stated mechanism refuted, not merely bounded. Density stands at
rank 1 of 10. Speed stands at rank 10 of 10, last by 15×. The remaining epic headroom is on the speed
branch.
