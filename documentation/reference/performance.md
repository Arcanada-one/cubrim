# Reference — Performance profile

Measured characteristics of the champion Cubrim codec (commit `6eaefad`, DB meta
12). Numbers are real measurements on representative text, single machine
(125 GB RAM, 16 cores), `/usr/bin/time -v` for peak RSS. See `PROVENANCE.md`.

> Cubrim optimises for **compression ratio**, not speed. The context-mixing (CM)
> codec is deliberately compute-heavy. Decompression is much faster than
> compression.

## Compression time (wall clock)

| input | wall time | note |
|-------|-----------|------|
| 100 KB | ~0.16 s | |
| 250 KB | ~0.48 s | |
| 500 KB | ~7.6 s | steep rise begins |
| 750 KB | ~13 s | |
| 1 MB | ~37 s | |
| 2 MB | ~4–6 min | ~8–9 cores busy |

Time grows **super-linearly**. Extrapolated: ~10 MB is tens of minutes, and
100 MB-class inputs (e.g. enwik8) run for hours. This is why separate
compress/decompress time metrics are part of the benchmark (branch C / C1).

## Peak memory (RSS)

| input | compress RSS | decompress RSS |
|-------|--------------|----------------|
| 100 KB | ~15 MB | ~5 MB |
| 500 KB | ~457 MB | |
| 1 MB | ~850 MB | ~800 MB |
| 1.5 MB | ~1.6 GB | |
| 2 MB | ~0.9 GB (plateau) | |

Memory is driven by the CM model hash-table size
(`tbits = clamp(ceil(log2(len)) + 3, 18, 27)` in `src/cm2.rs`), which the model
builds over the whole input. Because `tbits` caps at 27, **peak memory plateaus
in the ~1 GB range** — it does not grow unbounded with file size, and does not
OOM on a modern machine. `CUBR_THREADS` does **not** reduce peak memory (it is
model size, not parallelism).

## Practical guidance

- **Sweet spot: ~100 KB – 1 MB.** Cubrim wins clearly on ratio here (e.g. 1 MB
  text: 0.116 vs xz‑9 0.148, gzip‑9 0.232).
- **< ~64 KB:** may not beat gzip (small inputs skip the strong entropy path);
  round trip stays byte-exact, output never exceeds input + a small header.
- **> a few MB:** compression is impractical for interactive use; prefer it for
  archival/offline compression where ratio matters more than time.
- Compression is **deterministic** (same input → byte-identical output) and
  **stable** (verified over repeated round trips).

## Determinism & round-trip

Every operation is byte-exact on decode. The encoder is competitive-min: it
tries several schemes per input and keeps the smallest plus a scheme byte, so the
default already gives the best ratio and the round trip cannot lose data.
