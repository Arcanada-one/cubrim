# Cubrim v0.3.2 ratio benchmark reproducer

This package independently reproduces the 24-file, ten-archiver Cubrim world
ratio benchmark on Linux x86-64. Everything it needs is fetched from public
sources and checksummed; nothing private is required to run it.

## What it verifies

Every one of the 240 file/archiver cells must compress, decompress, and pass an
external byte comparison against the original. On top of that:

- **Nine of the ten archivers are held to exact archive sizes** — 216 cells,
  including **every Cubrim cell**.
- **rar is held to its round trip plus a 256-byte bound**, and any difference is
  printed and counted rather than absorbed. See below for why.

A run that meets this prints `"status": "PASS"` along with
`byte_exact_cells` and `rar_byte_deltas`. Partial, duplicate, unexpected, or
altered evidence fails. The verifier refuses a journal whose SHA-256 does not
match its sidecar.

Our own reference run produced `byte_exact_cells: 228`, `rar_byte_deltas: 12`.

## Why rar is treated differently

rar stores each source file's modification time and widens that encoding for
recent timestamps, so its archive size depends on how the corpus was copied
rather than on content alone. It is the only one of the ten archivers with that
property — the other nine are byte-identical given the same input.

Concretely, `canterbury/alice29.txt` compresses to 51,179 bytes with its
original 1996 timestamp and 51,195 with a recent one.

So `acquire.sh` **fails closed if extraction did not preserve the archived
timestamps**, and the verifier allows rar a 256-byte margin — sixteen times the
observed effect, and far below any real compression change. A rar result that
drifts further than that is rejected, not tolerated.

If you extract the corpora yourself, use a tool that restores stored mtimes
(plain `unzip`, not `unzip -DD`).

## What is pinned

- Ubuntu 24.04 amd64 base image, by OCI manifest digest.
- Open archiver package versions in `packages.lock`.
- Canterbury, enwik8, and Silesia download URLs and archive checksums.
- A 24-row corpus manifest with exact sizes and SHA-256 hashes.
- The public Cubrim v0.3.2 Linux x86-64 release archive and extracted binary
  checksums.
- RAR 7.00 vendor archive and binary checksums. RAR is downloaded only into your
  mounted workspace and is never baked into the image.
- Code-owned argv templates for all ten archivers. No downloaded or
  database-supplied text is ever executed as a command.

### Which Cubrim binary

The authoritative identifier is the binary hash, which `acquire.sh` verifies:

```
cubrim-v0.3.2-linux-x86_64.tar.gz
  sha256 cbf672e15e425032b6b9bcf28c1308650edb9b4de47d6e04a26414a038ed36fe
extracted cubrim
  sha256 b6c3cd251f7148c1895f5b85d30d06df8252a70afbd649e269f673a19e2a5768
```

Both match the `checksums.txt` published on the GitHub release. This binary
reports `cubrim 0.3.2`.

`archiver_templates.json` records `release_commit dfb195ef…`, which is the last
source commit before the version bump. The published v0.3.2 artifact was built
from `09ef2bbd…`, one commit later, whose entire diff is `CHANGELOG.md` plus
`version = "0.3.1"` → `"0.3.2"` in `Cargo.toml`. No compiled code differs
between them. Both are stated rather than one being quietly dropped.

## Expected ratios

Benchmark meta 35 stores most competitor file ratios to six decimal places and
does not store their integer archive sizes. This package does **not**
reverse-infer bytes from those rounded values. `expected_cells.json` is frozen
from a separate closed run whose encode, decode, and external byte comparison
all passed, and `expected_aggregates.json` preserves the database's published
ratio contract.

## Requirements

An x86-64 Linux host with Docker, at least 32 GiB of free memory, at least
10 GiB of free disk, and several hours of uninterrupted runtime. The Cubrim
phase is intentionally slow — our reference run took about 5.5 hours, of which
Cubrim was roughly 90%.

Do not compare elapsed time from this ratio reproduction against the separately
controlled timing benchmark; this run is not a timing measurement and is
deliberately resource-capped.

## Running it

Build the image:

```sh
sudo docker build --platform linux/amd64 -t cubrim-reproducer:latest .
```

Create a workspace:

```sh
install -d -m 0700 "$PWD/cubr-reproduction-workspace"
```

Acquire and checksum every runtime input:

```sh
sudo docker run --rm --platform linux/amd64 \
  -v "$PWD/cubr-reproduction-workspace:/workspace" \
  cubrim-reproducer:latest acquire
```

Read `cubr-reproduction-workspace/tools/RAR-LICENSE.txt` before using RAR. This
package reports the vendor terms; it does not interpret or accept them for you.

Run all 240 cells. Cubrim requires licence acceptance, and this package will not
accept on your behalf — pass `CUBRIM_ACCEPT_LICENSE=1` to confirm you accept the
terms it prints:

```sh
sudo docker run --rm --platform linux/amd64 \
  --memory=32g --cpus=4 \
  -e CUBRIM_ACCEPT_LICENSE=1 \
  -v "$PWD/cubr-reproduction-workspace:/workspace" \
  cubrim-reproducer:latest run
```

Without that variable the run stops before doing any work and prints the terms.
Note that Cubrim's licence and release fetches report an install id, IP address,
OS, architecture, and version to the vendor.

The run prints the closed journal and sidecar paths. Verify those exact paths:

```sh
sudo docker run --rm --platform linux/amd64 \
  -v "$PWD/cubr-reproduction-workspace:/workspace" \
  cubrim-reproducer:latest verify \
  --journal /workspace/results/RUN.journal.jsonl \
  --sidecar /workspace/results/RUN.journal.sha256.json
```

## Independent review invitation

Run this on a host we do not control and tell us what you get.

Please share the complete journal, the sidecar, the image build log, and your
host details. **A mismatch is useful evidence — report it without editing the
raw files.** If some cell does not reproduce, we would rather hear it from you
than not know.
