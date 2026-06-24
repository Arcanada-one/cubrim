# H-25j-full — binary-tree match finder (long-range measurement)

**Parent SHA (pre-commit baseline H-25j-lite):** 88812452e80e44bbef518cf78e52012506fd29bd
**Date:** 2026-06-24
**Lever:** LZMA-style BST suffix match finder (`bt_get_matches`) feeding the rep-aware
optimal DP (`lz77_parse_optimal`), as a superset of the hash-chain candidates.

## Method

Same regenerated deterministic in-repo fixtures as H-25j-lite (the H-25g..i ad-hoc
fixtures were never committed), so absolute bytes are NOT comparable to the H-25i
table — only the within-run baseline-vs-candidate delta on identical files is valid.
Each file: `cubrim compress` (auto MODE_LZ >64 KB), round-trip-verified, vs gzip-9 / zstd-19.

## Result (Cubrim bytes, RT PASS each)

| fixture | H-25i | H-25j-lite | H-25j-full | gzip-9 | zstd-19 | vs zstd |
|---|---:|---:|---:|---:|---:|---:|
| srctree.tar | 86288 | 86152 | 85398 | 93744 | 79569 | +8.4% → **+7.3%** |
| multiversion.bin | 61480 | 61412 | 61007 | 184642 | 56625 | +8.6% → **+7.7%** |
| repeated.log | 13123 | 11889 | 11774 | 24840 | 10063 | +30.4% → **+17.0%** |
| multicopy120k.bin | 5016 | 5017 | 5017 | 4798 | 3690 | +35.9% → +36.0% |

Zero regression on gated corpora: tuned 10-file **0.158273 (byte-identical)** RT 10/10;
holdout **0.2390 (byte-identical)** RT 6/6. Speed ~73 s / 1.9 MB (BT runs in addition to
the hash chain; research max-ratio path).

## Verdict

PROGRESS — the BT finder surfaces longer/cleaner matches the hash chain misses,
narrowing the zstd gap a further ~1% on mixed/near-duplicate data, regression-proof and
byte-exact (new adversarial RT test). Does NOT beat zstd uniformly: ~7–8% remains. With
match selection no longer the bottleneck, the residual floor is **offset coding** —
zstd's FSE offset-code + repcode vs Cubrim's LEB128-varint distance split through rANS.
Next lever (H-25k): an FSE/rANS offset-code model (bit-length bucket + context-coded
bucket + raw low bits). Leaderboard untouched; NOT tuned to any corpus.
