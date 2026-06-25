# H-25j-lite — repeat-offset-aware DP cost model (long-range measurement)

**Parent SHA (pre-commit baseline H-25i):** 0077d2b3aa2401c155e15256cee58ed86dd14188
**Date:** 2026-06-24
**Scheme:** MODE_LZ optimal parser (`lz77_parse_optimal` in codec.rs), rep-aware cost.

## Method

The H-25g..i ad-hoc long-range fixtures were never committed. Fixtures here are
**regenerated deterministically in-repo**, so absolute bytes are NOT comparable to
the H-25i hypothesis-log table — only the within-run baseline-vs-candidate delta on
the identical files is valid. Each file is compressed by `cubrim compress` (auto
MODE_LZ for >64 KB), round-trip-verified, and compared to gzip-9 / zstd-19.

| fixture | shape | bytes |
|---|---|---:|
| multiversion.bin | 3 git-historical codec.rs concatenated (near-duplicate) | 942063 |
| srctree.tar | tar of code/cubrim-rs/src (mixed cross-file) | 460800 |
| multicopy120k.bin | 12× a 10 KB block (pure duplicate) | 122880 |
| repeated.log | synthetic syslog, repeated lines (rep-offset rich) | 241424 |

## Result (Cubrim bytes, RT PASS each)

| fixture | H-25i base | H-25j-lite | Δ | gzip-9 | zstd-19 | vs zstd |
|---|---:|---:|---:|---:|---:|---:|
| repeated.log | 13123 | 11889 | **−9.4%** | 24840 | 10063 | +30.4% → **+18.1%** |
| multiversion.bin | 61480 | 61412 | −0.11% | 184642 | 56625 | +8.6% → +8.5% |
| srctree.tar | 86288 | 86152 | −0.16% | 93744 | 79569 | +8.4% → +8.3% |
| multicopy120k.bin | 5016 | 5017 | +1 B | 4798 | 3690 | +35.9% → +36.0% |

Zero regression on gated corpora: tuned 10-file **0.158273 (byte-identical)** RT 10/10;
holdout **0.2390 (byte-identical)** RT 6/6.

## Verdict

MARGINAL WIN on rep-offset-rich long-range (repeated.log −9.4%); regression-proof and
byte-exact. Does NOT beat zstd uniformly — the ~8% tarball/near-duplicate gap is
dominated by match-finder candidate density (cause a), the open H-25j-full lever
(binary-tree / suffix-automaton match finder). The +1 B on multicopy120k is a
parse-heuristic artefact on an untracked synthetic fixture (no gated corpus touched).
