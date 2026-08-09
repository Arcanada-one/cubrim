# Results: competed identity-init APM on the value-rail geomix coder (NEW-08, narrowed) — NO-GO

**State:** MEASURED, prediction refuted. Preregistration:
`CUBR-NEW08-APM-20260809.md` (main @ 4b8a03b, PR #56, landed BEFORE the
build). Implementation evidence: branch `cubr-new08-apm`, commit `5520985`
(pushed, unmerged — the codec change does not land). Probe basis that
motivated it: `probes-20260809/probe-new08-notes.md` (PR #55).

## Premise correction found during implementation

The prereg named `geocm.rs` as the likely site; the actual scheme-11
`BwtGeoMix` coder lives in `codec.rs` (`gm_mix_encode`/`gm_mix_decode`),
which quantises the mixed posterior straight into the range coder with no
SSE — the mechanism premise (no calibration stage on the value rail) was
correct, the file was not. Scheme 10 was not extended: its two coder modes
share no plumbing with geomix, and the F17/F18 attribution puts the mr/x-ray
nested wins on geomix.

## Implementation (for the record — fully gated, then refuted)

`GmApm`: 33-knot interpolated table over quantised stretch(p), 512 context
rows, virgin-cell tracking making the untrained stage a byte-exact no-op;
per-block competition emitting the APM arm only when strictly smaller; flag
in the high bit of the wire `lr_idx` byte, which the pre-change parse
rejects as out-of-range — fail closed, verified by test. Suite: baseline
361/0/11 → 365/0/11 (exactly the 4 new focused tests). +431/−13 lines,
`codec.rs` only.

## Measured outcome

Preset `max`, whole files, both binaries (pre-change base vs APM build),
round-trip `cmp` OK on all ten runs:

| file | base bytes | new bytes | Δ |
|---|---|---|---|
| mr | 2,071,530 | 2,071,530 | 0.00% |
| x-ray | 3,637,036 | 3,637,036 | 0.00% |
| dickens | 2,112,521 | 2,112,521 | 0.00% |
| sao | 3,810,052 | 3,810,052 | 0.00% |
| osdb | 2,187,994 | 2,187,994 | 0.00% |

All five pairs byte-identical; local ratios match the campaign lineage
(mr 0.20777, x-ray 0.42919).

**Prediction verdicts:** P1 (mr ≤0.20568) and P2 (x-ray ≤0.42490) FAIL at
0.0% improvement. P3 (everything else byte-identical-or-smaller) holds.
**P4's NO-GO rule fires** — bytes alone decide it; no stand bench is needed
and none was run.

## Why identical bytes are a measurement, not an inert path

Per the "identical bytes = probe the mechanism" lesson, a temporary
env-gated diagnostic (built, run, fully reverted; rebuild byte-identical to
the shipped test binary) on a real 4 MB mr slice showed **768 of 768 geomix
blocks encode the APM arm and lose every one** — min +236 B (~+1.5%), mean
+1031 B (+6.3%), 0 wins, 0 ties. The competitive-min construction contained
the damage to exactly 0 bytes, as designed.

## Mechanism finding (the transferable lesson)

The probe's +4.4–10.6% came from calibrating a deliberately weak order-1
bitwise analogue. The real geometric o2/o1/o0 mix with online weight
learning is **already calibrated** — an added APM stage only injects coding
noise, and even the best block loses by ~1.5%, so no parameter retuning
inside the preregistered design closes the gap (and tuning beyond it would
be post-hoc). Corollary for future probes: **an analogue-calibration gain
transfers only if the real coder lacks the calibration pathway; when the
real coder learns its mixture online, analogue headroom is an artifact.**
This is the second probe-class correction of the day (with Gotcha #6's
branch-count rule) and belongs in the gotcha ladder if it recurs.

## Disposition

- Branch `cubr-new08-apm` stays unmerged as evidence; the wire is unchanged
  on `main`; no preset gains an APM.
- NEW-08's hypothesis row: → `closed`, NO-GO by real-codec refutation of
  the narrowed scope (the broad scope was already empty per PR #55).
- Encoder-cost note for any future revival: the competed integration codes
  every geomix block twice (~2× geomix encode) — that price bought exact
  containment here and would need restating in any new prereg.
- No DB throughput rows; no site work; `evaluation` untouched.
