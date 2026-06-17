---
artifact: research-measurement
task_internal: prototype-first-measurements
created: 2026-06-17
status: measured
corpus: synthetic-fixed-seed
---

> 🔒 **СЕКРЕТНО — внутренний артефакт.** Результаты замеров Cubrim-прототипа.
> Живёт ТОЛЬКО в `docs/ephemeral/research/` (приватный репо). Механизм НЕ публикуется.

# Cubrim v1 Python Prototype — First Measurements

Prototype: Python 3 + NumPy. Algorithm: rulebook v1 (R1–R8).
Corpus: synthetic, fixed seed, reproducible via `make benchmark`.

## AC-2: Raw-store fallback on 1 MB uniform-random input (DeepSeek test)

R7 mandatory: if cube_size >= raw_size + header_overhead → mode=1 (raw-store).

| Metric | Value |
|--------|-------|
| Input size | 1,048,576 bytes |
| Output size | 1,048,589 bytes |
| Ratio (output/input) | 1.000012 |
| Mode | 1 (raw-store) |
| Overhead bytes | 13 |
| HEADER_OVERHEAD_BOUND | 320 bytes |
| Round-trip | PASS |

**H-09 verdict:** R7 raw-store confirmed.
Expansion ratio 1.0000 <= 1.1x (within bound).

## AC-3: Gap=1 locality stats on baseline corpus (Moonshot test)

N=2 cube, mixed-radix Φ. Per-axis gap sequences measured.
If mean run-length < 8 → confirms consilium locality risk → OQ-3/OQ-5 prioritised over OQ-2.

| File | Total Gaps | Fraction(gap=1) | MeanRun(gap=1) |
|------|-----------|-----------------|----------------|
| text_64kb       |        512 |      1.0000 |    512.00 |
| random_64kb     |        512 |      1.0000 |    512.00 |
| log_16kb        |        320 |      1.0000 |    320.00 |

| **aggregate** | — | **1.0000** | **448.00** |

**H-02/H-04/H-06 evidence:**
- Mean fraction(gap=1): 1.0000
- Mean run-length(gap=1): 448.00
- mean run-length >= 8 → locality baseline acceptable

## AC-4: First compression ratio on locality corpus

| File | Input (B) | Output (B) | Ratio | Mode | RT |
|------|-----------|-----------|-------|------|-----|
| text_64kb       |     65,536 |     41,025 |  0.6260 | cube      | OK |
| random_64kb     |     65,536 |     65,549 |  1.0002 | raw-store | OK |
| log_16kb        |     16,384 |     12,379 |  0.7556 | cube      | OK |

| **aggregate (cube only)** | — | — | **0.6908** | — | — |
| **aggregate (all)** | — | — | **0.7939** | — | — |

**H-01/H-03/H-08 evidence:**
- Mean ratio all files: 0.7939
- ratio <= 0.9 on some files → some compression benefit observed
- Mean ratio cube-mode only: 0.6908

## Reproducibility

```bash
cd Projects/Cubrim/code
make benchmark
```

Corpus: synthetic, numpy fixed seeds (text=fragment*rep, random=np.random.default_rng(777),
log=templates*rng(99)). No external files required.
