# Results: Fast-CM model-set tier ladder (NEW-24) — P-A..P-D adjudicated

**State:** MEASURED. Preregistration: `CUBR-NEW24-TIERS-20260809.md` (main @
PR #58, landed before the build). Implementation: this branch
(`cubr-new24-tiers`, commits fba3f88 + 285ab26), based on main 472be81.
Density-cost probe basis: `probes-20260809/probe-new24-notes.md`. Raw
evidence: `new24-tiers-20260811/` (density diagnostics, P-A journal, bench
script).

## Implementation summary

`Cm2Tier {Full, F12, M8, M8S}` recorded in the CM2 length header at bits
45..47 — **inside the length field above `MAX_DECODE_LEN`**, so a pre-change
decoder computes an implausible `orig_len` and rejects in O(1): fail-closed
verified against a real pre-change binary (exit 2, no output, exact error
recorded). Header charge is exactly **0 bytes** (unit-pinned). Reduced tiers
have models **structurally absent** — no tables, no probes, no write-backs,
L1 mixers constructed at nin 22/15/19 vs 50 — so all three measured cost
centres shrink together. Encoder: `CUBR_CM2_TIER` emits the tiered candidate
beside full CM2 under a guard (shipped stream never exceeds full + 0 B);
`CUBR_CM2_TIER_FORCE=1` is the explicit density-for-speed escape. No-knob
output is **byte-identical** to the pre-change build (xml/dickens/osdb whole
files; dickens `b39d5043…` and xml `d64f83f3…` equal the Phase C campaign
canonical hashes). Suite: 329+11 lib (baseline+7), integration green, clippy
clean.

## P-A (speed) — CONFIRMED, above the map

dev-ai stand, pin 16–19, campaign thread semantics, per-cell
`systemd-run --scope` memory caps (14G full / 8G tiered), quiet gate, 3 reps
per cell, every rep round-tripped `cmp`+sha256 clean, zero gate failures.
Medians, same binary (`d6f06d07…`), same host, same pin:

| cell | archive | median wall | speedup | floor | map |
|---|---|---|---|---|---|
| dickens full | b39d5043… (canonical) | 101.04 s | — | — | — |
| dickens F12 | ca2495c2… | 45.18 s | **2.24×** | ≥1.5× ✓ | 1.81× |
| dickens M8 | 21ae7e34… | 30.00 s | **3.37×** | ≥2.0× ✓ | 2.35× |
| osdb full | 29b78b90… | 109.24 s | — | — | — |
| osdb M8S | 370e340b… | 39.50 s | **2.77×** | — | — |

**Exceeding the map, explained by mechanism (protocol rule 5):** the map
model (`1/(0.17+0.83·n/26)`) scaled probe count linearly while holding
per-probe cost fixed. Dropping 14 of 26 tables also shrinks the table
working set (~13.5 → ~6 GiB at `tbits=27`-class inputs), which reduces the
LLC/TLB miss latency of every *remaining* probe — exactly the stall term the
decode-attribution map showed carries the budget. Consistency evidence: the
tiered decode cells ran inside an 8 GiB memory cap while the full cells
required a 14 GiB cap. This explanation is consistency-verified, not
independently proven; a per-tier RSS/miss-counter measurement would close it
and is left as an open follow-up, not assumed.

Honest fraction of ceiling: F12's 2.24× is 38% of the ~5.9× n→0 model bound
and 16% of the ~14× full-replacement outer bound. The tier ladder is a real
lever, not the endgame.

## P-B (density, F12) — REFUTED on 2 of 5 files, exactly along the owned risk

Whole files, `max` tables, full-vs-tiered stream sizes from the same encode
(`CM2-TIER` diagnostics, raw logs in the record dir):

| file | F12 Δ | threshold | verdict | lead allowance | lead |
|---|---|---|---|---|---|
| dickens | **+3.58%** | ≤+3% | **FAIL** | +8.72% | survives (41% consumed) |
| xml | +4.14% | ≤+11% | pass | +27.29% | survives (15%) |
| samba | +1.82% | ≤+5% | pass | +19.13% | survives (10%) |
| osdb | **+8.85%** | ≤+8% | **FAIL** | +9.08% | survives (97% consumed) |
| enwik8-head32m | +1.73% | ≤+5% (head sample) | pass | +14.58% | survives (12%) |

The preregistration's named primary risk — whole-file densities above the
1 MiB slice deltas — materialized on exactly the two files whose slice
numbers were most optimistic (dickens 3.4× its slice delta). Per its own
wording this is a clean refutation of F12-as-universal-default: **F12 is a
class-conditional tier**, safe on code/markup/large-text, marginal on
database (97% of allowance) and above threshold on dense prose.

## P-C (guarded integration, M8) — SUPPORTED by behaviour

- M8 densities: dickens +8.00% (lead survives, 92% consumed), xml +8.62%,
  samba +4.57%, enwik8-head +6.08% (42% of allowance) — and **osdb +9.51%,
  lead LOST** (allowance +9.08%).
- The guard did its job on the lead-losing cell: the unforced osdb M8 run
  demonstrably shipped the full-CM2 stream (archive = full blob + container
  bytes). M8S (+ sparse g(1,3)/g(2,3)) recovers osdb to **+6.50%**,
  confirming the database-class sparse rule from the probe.

## P-D (wire) — CONFIRMED

Exactly one new decoder branch; reserved tier values and tier+column
combinations fail closed; tier-less parse bit-identical; header charge 0 B;
old decoder rejects tiered archives in O(1) without allocation.

## Product disposition (decided under the autonomous mandate, both sides stated)

1. **This branch lands on `main`** — knob-gated, default output byte-identical,
   regression-proof by gates above. Landing changes nothing for any user or
   benchmark by default and puts the tier machinery and its evidence in-tree.
2. **No preset adopts a tier yet.** The measured trade (2.24–3.37× decode for
   +1.7–8.9% density, class-dependent, lead retained at F12 everywhere
   measured) is real but touches the public operating point; adopting it in
   `balanced`/`web`/a new `fast` preset requires its own preregistered
   world-benchmark campaign (all 24 files, canonical timing pass, DB metas),
   which is the natural next NEW-24 stage. Per-file speed numbers here are
   pinned-run comparisons, valid as ratios, not campaign timing.

## Voids

- enwik8-head32m F12 and M8 density cells were measured by the coordinating
  session after the lane's own enwik8-head worker died at start (both
  attributed as such in the raw logs); full-enwik8 (100 MB) densities and
  any full-corpus P-B re-check belong to the future preset campaign.
- Per-tier decode RSS/miss counters (the mechanism-closure measurement for
  the above-map speedups): not measured; open follow-up.
