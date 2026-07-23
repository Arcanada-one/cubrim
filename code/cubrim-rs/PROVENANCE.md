# Cubrim CLI Provenance

Release line: **Cubrim-2 industrial** (world-benchmark champion, DB meta 12).

## Benchmarked codec

The compression/decompression codec shipped by this CLI is the champion measured
in the world benchmark and published to the results database:

- Champion codec commit: `6eaefad7e165cd74f7d660aeb6d0828bfbe12c41`
- Benchmark / DB snapshot: meta `12`, task `CUBR-0064-full24-cm2-retained-min`
  (published 2026-07-22, `is_current = 1`)
- Corpus: the 24-file world corpus (silesia / enwik8 / canterbury), 6 types
  (text, code, exe, binary, image, database)
- Round-trip: byte-exact (`cmp = 0`) on every measured file; competitive-min
  (the encoder emits `min` over its schemes plus a scheme byte, so the default
  path is always the smallest — see `src/config.rs` and Gotcha #4)

## Industrial release surface

This release branch (`research/cubr-branch-C-industrial`) adds **only** the
user-facing industrial surface on top of the champion commit:

- CLI ergonomics (`src/cli.rs`, `src/main.rs`): decluttered `--help` (research
  knobs hidden), human-readable stats line with separate compress/decompress
  timing and throughput, documented exit codes.
- Docs, smoke tests, and the macOS build/packaging scripts.

**No codec file is modified.** `src/codec.rs`, `src/cm2.rs`, `src/config.rs`,
`src/header.rs`, `src/huffman.rs`, `src/cube.rs`, `src/phi.rs`,
`src/distance_map.rs`, `src/rle.rs`, `src/bitpack.rs` are byte-identical to
`6eaefad`. The wire-format version byte (`header.rs: VERSION = 1`) is a hardcoded
constant independent of the package version, so the compressed byte stream is
identical to the benchmarked binary. This is verified by the `differential`
test suite and by direct byte comparison of compressed output.

## Reproducing the release build

```sh
# Confirm no codec file diverges from the champion commit (must print nothing):
git diff --name-only 6eaefad7e165cd74f7d660aeb6d0828bfbe12c41 -- \
  code/cubrim-rs/src/codec.rs code/cubrim-rs/src/cm2.rs \
  code/cubrim-rs/src/config.rs code/cubrim-rs/src/header.rs

# Build toolchain used for this handoff: rustc 1.97.1 (stable).
cargo build --release
```

## License

Cubrim is licensed for non-commercial use under PolyForm Noncommercial License
1.0.0 with Cubrim-specific notices in `LICENSE`.

Commercial use requires a separate Arcanada commercial license. The draft
commercial terms are in `LICENSE-COMMERCIAL.md`; the standard target is USD 50
per year per named user seat or per installed computer/device.

Temporary canonical publication target: `https://cubrim.com/legal/cubrim-license`.
Future canonical publication target: `https://legal.arcanada.ai/policies/cubrim/license/v1.0`.
