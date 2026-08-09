# Preregistration: Fast-CM model-set tier ladder (NEW-24)

**State:** PREREGISTERED DESIGN — no implementation or measurement result is
recorded here. Committed to `main` before the candidate is built, per
protocol. Bases: the measured decode-attribution map
(`CUBR-DECODE-ATTRIB-20260809-results.md`, PR #54) and the density-cost probe
(`probes-20260809/probe-new24-notes.md` + `probe-new24-journal.jsonl`, this
PR — 40 ablation cells, 5 calibration cells, calibration factors 1.10–1.18,
all within the 1.5× gate).

## Mechanism

A **wire-recorded model-set tier** for MODE_CM2: one tier field in the CM2
length header (exactly one new decoder branch — Gotcha #6; the archive grows
by exactly the header charge). The decoder builds only the recorded model
set, which shrinks the three dominant measured cost centres together: 23-way
probe-load latency (~50% of decode cycles), `Ctr::upd` write-back (~33%), and
mixer width (part of the remaining ~7%).

Tiers committed by the probe:

- **TIER F12** = {orders 0–7, word1, m1, m2, m3} — 12 probed models.
  Map-predicted decode speedup 1.81×; probe density cost ≤65% of the
  meta-36 lead allowance on every class measured.
- **TIER M8** = {orders 0–4, word1, m1, m3} — 8 probed models, plus sparse
  {g(1,3), g(2,3)} auto-added when the input classes as database/record
  (probe: sparse alone carries +5.13% on osdb). Map-predicted 2.35×.
- TIER S(5) is **NO-GO** (probe: loses the meta-36 lead on 4/5 CM2-won
  files) and is not implemented.

## Integration (product shape, stated up front)

Tier selection is **encoder-side and guarded**: a tiered encode is
accompanied by the full-CM2 encode (CM2 is already one candidate among many;
encode-side cost is the price of a decode-speed artefact), and the shipped
CM2 stream must never be larger than the full-CM2 stream by more than the
tier header charge unless the operator's preset explicitly buys density for
speed. `--preset max` output is unchanged by default. Whether a tier becomes
a shipping preset default (`balanced`/`web`/new `fast`) is a **product
decision taken after measurement** — this experiment produces the two-sided
numbers (density cost AND decode speedup, per file), not the choice.

Wire compatibility is one-directional like the `web` tbits field: archives
that select a tier need a decoder that reads the field; old decoders MUST
fail closed on it. Tier-less archives remain byte-identical to today's.

## Ceilings (stated before build)

From the attribution map with the fixed ~17% held out
(speedup(n) = 1/(0.17 + 0.83·n/26)): F12 → 1.81×, M8 → 2.35×; outer bounds
~5.9× (n→0) and ~14× (full CM2 replacement). Density ceilings per file =
the meta-36 lead allowance vs the best non-cubrim archiver: dickens +8.72%,
xml +27.29%, samba +19.13%, osdb +9.08%, enwik8 +14.58%.

## Falsifiable predictions

Real codec, whole Silesia files + enwik8, `max`-preset tables, byte-exact
round-trip on every observation, quiet-stand bench (pin 16–19, campaign
thread semantics):

- **P-A (speed):** TIER F12 decodes dickens/max ≥1.5× faster than full CM2
  (map predicts 1.81×); TIER M8 ≥2.0× (map predicts 2.35×). Below the floor
  = the speed model is refuted.
- **P-B (density, F12):** whole-file ratio worsening ≤ +3% dickens, ≤ +11%
  xml, ≤ +5% samba, ≤ +8% osdb, ≤ +5% enwik8 (probe deltas + slice
  extrapolation margin), AND the meta-36 lead survives on all five. Any
  lost lead = F12 refuted as a default tier on that class.
- **P-C (density, M8):** lead survives on dickens, samba, enwik8; on xml
  and osdb M8 may exceed its margin — the guarded selection must then fall
  back (F12 or full), and the shipped archive must never exceed the
  full-CM2 archive by more than the tier header charge. Violation = the
  guarded integration is refuted.
- **P-D (wire):** exactly one new decoder branch; archive grows by exactly
  the header charge on tier-selected files; old decoder fails closed on a
  tiered archive. More branches or silent decode = unsound.

**Known primary risk, owned by this experiment:** the probe measured 1 MiB
head slices; deep models train better at 10–100 MB, so whole-file density
costs are plausibly higher than the slice deltas. P-B's thresholds carry
margin for this; if whole-file costs still exceed them, that is a clean
refutation, not a calibration excuse. The hypothesis's original tier M with
1–2 sparse models (n≈9–10) was not measured as its own probe cell
(bracketed by the 17- and 8-model cells); the implementation sweep must
measure it directly.

## Gates

- `cargo test --release` green at base pass count + the new focused tests
  (tier round-trip per tier; fail-closed on a tiered archive under the old
  parse; tier-less byte-identity vs the pre-change build).
- Round-trip `cmp` + sha256 on all 24 meta-36 corpus files at every tier
  measured.
- Per-file figures only; no corpus aggregate; Canterbury excluded from
  claims.
- Bench on the quiet dev-ai stand only; voids to the run journal, never the
  DB; `evaluation` untouched; NEW-24's row updated only when the results
  record lands.
- Density and speed are BOTH reported per file per tier — a tier that trades
  one for the other is a product decision and is presented as such.
