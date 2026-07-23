# Changelog

All notable user-facing changes to the Cubrim CLI. This project keeps the
compression **codec** frozen at the world-benchmark champion (see
`PROVENANCE.md`); entries below are industrial-surface changes only unless a
codec change is explicitly called out.

The format is loosely based on [Keep a Changelog]. Dates are UTC.

## [Unreleased] — Cubrim-2 industrial

Codec: champion commit `6eaefad` (DB meta 12,
`CUBR-0064-full24-cm2-retained-min`). Compressed byte stream unchanged.

### Added
- Industrial CLI smoke tests (`tests/cli_compress_smoke.rs`): edge-input round
  trips (empty, single byte, incompressible random), deterministic-output
  check, documented exit codes (1/2/3), and the `--quiet` contract.
- `CHANGELOG.md` and a release checklist (`docs/release-checklist.md`).
- Throughput (MB/s) in the compress/decompress stats line.

### Changed
- `--help` decluttered: the research/tuning knobs (`--b`, `--n`,
  `--gap-scheme`, `--value-scheme`, `--raw-store-bound`, `--min-ctx-count`) are
  now hidden. They remain functional for reproducing research sweeps but no
  longer clutter the user-facing help. The default path already selects the
  competitive-min champion, so no flags are needed for best ratio.
- Stats line is now human-readable and reports compress and decompress timing
  **separately**, each with throughput, e.g.
  `compressed: 1000000 -> 116099 bytes  ratio 0.1161 (8.62x smaller)  11.9 MB/s  compress 84 ms`.
- Subcommand help wording: single-file `compress`/`decompress` are described as
  the primary Cubrim (`.cub`) codec (previously mislabelled "legacy blob").
- `PROVENANCE.md` updated to the meta-12 champion (`6eaefad`) with an explicit
  no-codec-file-changed guarantee.

### Known limitations (documented, not regressions — see README performance profile)
- Cubrim is tuned for inputs larger than ~64 KB. Files below the cube size
  limit (b² = 65536 bytes) fall back to a light path and may not shrink — a 5 KB
  text file compresses to ~0.90 where gzip‑9 reaches ~0.39. Round trip stays
  byte-exact; output never exceeds input + a small header. Improving small-file
  ratio would be a codec change (out of scope for this industrial branch;
  flagged to the codec branches).
- The context-mixing (CM) codec is compute-heavy and its compress time grows
  super-linearly: measured ~0.2 s at 100 KB, ~37 s at 1 MB, ~4–6 min at 2 MB
  (multi-core). Files beyond a few MB are impractical for interactive use.
  Decompression is much faster. Peak memory plateaus in the ~1 GB range (bounded
  by the CM model size, not linear in file size; `CUBR_THREADS` does not reduce
  it). Practical sweet spot: ~100 KB – 1 MB. Wall-clock timing is reported per
  operation; use `--quiet` in scripts.

[Keep a Changelog]: https://keepachangelog.com/
