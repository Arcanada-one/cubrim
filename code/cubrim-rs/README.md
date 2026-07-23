# Cubrim

Cubrim is a lossless compressor and `.cbr` archiver built around a
context-mixing codec. On the 24-file world benchmark it is the top-ranked
archiver by compression ratio across all six data types (text, code, exe,
binary, image, database). See `PROVENANCE.md` for the exact benchmarked commit
and database snapshot.

> **Round-trip is byte-exact.** Decompressing a Cubrim file always reproduces the
> original bytes. If it cannot, it fails loudly rather than returning wrong data.

## Install (macOS)

The macOS build is a universal (arm64 + x86_64) binary, ad-hoc signed. Because
it is not notarized, Gatekeeper quarantines it on first run — clear the flag or
right-click → Open once:

```sh
xattr -d com.apple.quarantine ./cubrim   # or: right-click the binary → Open
chmod +x ./cubrim
./cubrim --version
```

Verify the download against its published SHA-256:

```sh
shasum -a 256 ./cubrim   # compare with the value on the download page
```

## Usage

### Single files

```sh
cubrim compress  report.pdf report.pdf.cub    # compress one file
cubrim decompress report.pdf.cub report.pdf   # restore it (byte-exact)
```

The compress command prints a one-line summary to stderr:

```
compressed: 1000000 -> 116099 bytes  ratio 0.1161 (8.62x smaller)  11.9 MB/s  compress 84 ms
```

`ratio` is compressed ÷ original (smaller is better). Compress and decompress
timing are reported separately. Pass `-q` / `--quiet` to suppress the line.

### Archives

```sh
cubrim a backup.cbr photos/ notes.txt   # create a .cbr archive
cubrim x backup.cbr -o restored/        # extract
cubrim l backup.cbr                     # list contents
cubrim t backup.cbr                     # verify integrity without extracting
```

Run `cubrim --help` for the full command list.

## Exit codes

| code | meaning |
|------|---------|
| 0 | success |
| 1 | usage or input error |
| 2 | integrity / corrupt input / decode / authentication failure |
| 3 | filesystem I/O error |

## Performance profile (measured, honest)

Cubrim trades speed for ratio — the context-mixing codec is compute-heavy. Real
measurements on representative text (single machine, champion binary):

| input size | compress ratio vs gzip‑9 | compress wall time | peak RSS |
|-----------|--------------------------|--------------------|----------|
| 5 KB      | 0.90 vs **0.39** (worse) | <1 ms              | ~15 MB   |
| 100 KB    | 0.28 ≈ gzip 0.27         | ~0.2 s             | ~15 MB   |
| 1 MB      | **0.12** vs gzip 0.23 (beats xz‑9 0.15) | ~37 s | ~850 MB  |
| 2 MB      | (wins on ratio)          | ~4–6 min           | ~0.9 GB  |

Practical guidance:

- **Sweet spot: ~100 KB – 1 MB.** Cubrim wins clearly on ratio there.
- **Below ~64 KB** Cubrim may not beat (or even match) gzip — small inputs skip
  the strong entropy path. The round trip is still byte-exact and output never
  exceeds the input by more than a small header.
- **Above a few MB** compression time grows super-linearly and becomes
  impractical for interactive use (tens of minutes for 10 MB+). Decompression is
  much faster than compression. Peak memory plateaus in the ~1 GB range (it does
  not grow unbounded with file size).

Compression is deterministic: the same input always yields byte-identical
output.

## Documentation

Docs follow the [Diátaxis](https://diataxis.fr/) taxonomy:

- `documentation/tutorials/` — getting started
- `documentation/how-to/` — task recipes (e.g. reproduce a benchmark ratio)
- `documentation/reference/` — CLI (`docs/cli.md`), format and architecture
- `documentation/explanation/` — why the cube/CM model

Provenance and reproducibility: `PROVENANCE.md`. Release process:
`docs/release-checklist.md`. Changes: `CHANGELOG.md`.

## License

Non-commercial use under PolyForm Noncommercial 1.0.0 (see `LICENSE`). Commercial
use requires an Arcanada commercial license (`LICENSE-COMMERCIAL.md`).
