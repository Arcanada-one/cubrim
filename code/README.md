# Cubrim v1 Python Prototype

## Rust CLI Archiver

The Rust crate at `code/cubrim-rs` provides the release CLI:

```sh
cubrim compress input.bin input.cub
cubrim decompress input.cub restored.bin
cubrim a archive.cbr dir file.txt --force
cubrim x archive.cbr -o restored
cubrim l archive.cbr
cubrim t archive.cbr
```

Full CLI, container, crypto, and release handoff docs live in:

- `code/cubrim-rs/docs/cli.md`
- `code/cubrim-rs/docs/cubrim-archive-format.md`
- `code/cubrim-rs/docs/crypto.md`
- `code/cubrim-rs/docs/release.md`

Research prototype of the Cubrim compression algorithm, strictly tracing rulebook v1 (R1–R8).

This is a **research instrument**, not production code. Its purpose:
1. Prove lossless byte-exact round-trip (cornerstone invariant).
2. Run the two first measurements recommended by the consilium.
3. Record the first compression ratio baseline.

## Quick Start

```bash
cd Projects/Cubrim/code
make test       # run all tests
make benchmark  # run measurements → docs/ephemeral/research/CUBR-0004-first-measurements.md
```

## Module Map

| Module | Rule | Role |
|--------|------|------|
| `phi.py` | R1 | Mixed-radix index↔coordinates bijection |
| `cube.py` | R1, R2 | Sparse cube construction |
| `distance_map.py` | R3, R3.1 | Per-axis gap encoding with sentinel −1 |
| `rle.py` | R4 | Pure RLE of gap streams |
| `bitpack.py` | R5 | Shift-to-corner + fixed-width bit-packing |
| `header.py` | R6 | Self-describing binary header |
| `codec.py` | R6, R7 | Top-level encode/decode + raw-store fallback |
| `domainize.py` | R8 | Bytes-as-is domain layer |

## Tests

```
tests/test_round_trip.py         — V-AC-1 cornerstone: sha256 byte-exact round-trip
tests/test_gap_invariant.py      — R3.1 fail-closed: gap=0 and gap>b_k raise
tests/test_decode_robustness.py  — V-AC-4: corrupt input raises, never silent garbage
tests/test_raw_store.py          — AC-2: random input → raw-store mode engaged
tests/test_traceability.py       — AC-5: every module has a rule reference
```

## Stack

Python 3.10+, NumPy, pytest. No C extensions. No zstd/LZMA in the encoder.
