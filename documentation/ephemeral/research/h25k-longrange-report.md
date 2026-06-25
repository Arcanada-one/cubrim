# H-25k — FSE/rANS offset-code model (long-range measurement)

**Parent SHA (pre-commit baseline H-25j-full):** 01617c8cf376fa24ffc6755b8cbcbe2e9391e454
**Date:** 2026-06-24
**Lever:** `seq_format = 2` offset-code coder — new distances split into a bit-length
code (rANS-coded) + raw low bits, behind the competitive min over seq_formats {0,1,2}.

## Method

Same regenerated deterministic in-repo fixtures as H-25j (the H-25g..i ad-hoc fixtures
were never committed), so absolute bytes are NOT comparable to the H-25i table — only
the within-run baseline-vs-candidate delta on identical files is valid. Each file:
`cubrim compress` (auto MODE_LZ >64 KB), round-trip-verified, vs gzip-9 / zstd-19.

## Result (Cubrim bytes H-25j-full -> H-25k, RT PASS each)

| corpus | H-25j-full | H-25k | vs zstd-19 | seq_format |
|---|---:|---:|---:|---|
| multicopy120k.bin | 5017 | 4448 | 3690 = +20.5% (was +36.0%) | 2 (offset-code) |
| multiversion.bin | 61007 | 61007 | 56625 = +7.7% | 0 (separate) |
| srctree.tar | 85398 | 85398 | 79569 = +7.3% | 0 (separate) |
| repeated.log | 11774 | 11774 | 10063 = +17.0% | 0 (separate) |

Zero regression on gated corpora: tuned 10-file **0.158273 (byte-identical)** RT 10/10;
holdout **0.2390 (byte-identical)** RT 6/6. cargo test 229 passed.

## Verdict

MARGINAL WIN on pure-duplicate (multicopy −11.3%, gap to zstd nearly halved),
regression-proof and byte-exact. Does NOT close the diverse-offset gap: on srctree /
multiversion / repeated.log the EXISTING separate per-stream distance coder
(seq_format 0 — byte-split + order-1 rANS context) already beats both the combined
varint (1) and the offset-code (2). The H-25j-full "offset coding is the floor"
diagnosis was half-right: Cubrim was already coding offsets competitively; the
bit-length-bucket + raw-low-bits split only helps where distances leaving the combined
buffer let the structural stream model cleanly (pure-duplicate). Offset coding is NOT
the residual lever. Remaining gap is parse/match-count + literal entropy (diminishing
returns). Leaderboard untouched; NOT tuned to any corpus.
