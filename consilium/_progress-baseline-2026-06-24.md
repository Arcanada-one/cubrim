# Progress baseline — night of 2026-06-23 → morning 2026-06-24

Reference point so "+10% by morning" is a measured delta, not a vibe.

## GOAL ESCALATED (operator 2026-06-24, after H-25g)

"мы теперь конкурируем с лучшим на планете! продолжай до полной победы!" — the target is no
longer "match gzip" or even "match zstd". The target is to **BEAT zstd-19 (best-on-planet)**.
Push + PR + dashboard publish are now AUTONOMOUS (gate lifted). Progress now = beating zstd on
more data shapes.

Status at escalation: Cubrim already BEATS zstd-19 on repeated.log (−18%, via BWT chunked),
TIES on pure-duplicate (0.17%), within ~10% on near-duplicate, +11% behind on a mixed tarball.
Full win = beat zstd uniformly on long-range AND move the diverse holdout (currently +1.30%
behind gzip, the BWT-family ceiling — needs a genuinely new lever there).

## Where we are at baseline (this snapshot)

- **Champion (tuned 10-file corpus):** BwtGeoMix 0.158273 — edges gzip 0.159674 by 2 B, but FRAGILE/corpus-specific.
- **Honest holdout aggregate (disjoint 6-file, the number that matters):** Cubrim 0.2390 vs gzip 0.2359 vs zstd-19 0.2214.
  - Cubrim is **+1.30% BEHIND gzip** and +7.95% behind zstd on unseen data. This is the real frontier.
- **Scalability:** 64KB ceiling REMOVED (chunked + SA-IS); >64KB files compress + round-trip byte-exact. Done.
- **In flight:** H-25 LzRans (scheme-12) — LZ77 match modeling, the first idea with a generalising-win path (probe info-floor −24% under gzip on holdout, gated on distance-stream entropy quality).

## What "+10% progress" means (pick the honest metric, not cherry-pick)

The headline metric is the **honest holdout aggregate vs gzip** (currently +1.30% behind). Real progress =
moving that gap. Concretely, by morning a credible 10%+ step is ONE of:

1. **H-25 lands a measured holdout win** (LzRans realises any fraction of the −24% probe floor → Cubrim goes from +1.30% behind gzip to ahead on unseen data). This would be the real breakthrough, not a corpus-overfit.
2. **H-25 measured NO-GO with an honest root-cause** + the NEXT hypothesis probed (progress = the search advanced, dead-end ruled out with evidence, not ratio).
3. If H-25 partially works (beats gzip on some holdout files, not aggregate): report the per-file wins as the delta.

NOT progress: another tuned-corpus micro-win that doesn't generalise (we already have one; the holdout proved it's not real).

## Baseline numbers to diff against in the morning

| metric | baseline |
|---|---|
| holdout aggregate Cubrim | 0.2390 |
| holdout aggregate gzip-9 | 0.2359 |
| holdout aggregate zstd-19 | 0.2214 |
| Cubrim vs gzip (holdout) | +1.30% behind |
| holdout files Cubrim beats gzip | 2/6 (prose marginal, csv) |
| tuned-corpus champion | 0.158273 (BwtGeoMix) |
| highest closed hypothesis | H-24; H-25 in flight |
| scalability ceiling | removed (chunked+SA-IS) |

Morning check: re-read CUBR-CONT-STATUS.md tail for the H-25 verdict, diff holdout aggregate, report the honest delta.
