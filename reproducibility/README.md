# Cubrim v0.3.2 ratio benchmark reproducer

This package independently reproduces the 24-file, ten-archiver Cubrim world
ratio benchmark on Linux x86-64. Everything it needs is fetched from public
sources and checksummed; nothing private is required to run it.

## What it verifies

Every one of the 240 file/archiver cells must compress, decompress, and pass an
external byte comparison against the original. On top of that:

- **Nine of the ten archivers are held to exact archive sizes** — 216 cells,
  including **every Cubrim cell**.
- **rar is held to its round trip plus a 32-byte bound**, and any difference is
  printed and counted rather than absorbed. See below for why.

A run that meets this prints `"status": "PASS"` along with
`byte_exact_cells` and `rar_byte_deltas`. Partial, duplicate, unexpected, or
altered evidence fails. The verifier refuses a journal whose SHA-256 does not
match its sidecar.

## Result of our reference run

A full containerised rebuild (run `cubr0069-20260728T175301Z`, 240 samples,
sidecar present) compared against the canonical measurement journal:

| | cells | result |
|---|---|---|
| Cubrim | 24 | **bit-identical** |
| all other non-rar archivers | 192 | **bit-identical** |
| rar — canterbury + enwik8 | 12 | **bit-identical** |
| rar — silesia | 12 | uniformly **−16 bytes** |
| round-trip failures | — | **zero** |

The **1–10 ranking is unchanged**. Even rar's overall aggregate moves only in
the sixth decimal, 0.257369 → 0.257368; every other archiver's aggregate is
identical to the last digit.

So the honest claim is: *an independent containerised rebuild reproduces every
archiver bit-exactly except rar, whose 16-byte-per-file delta is a documented
mtime artefact, and the ranking is unchanged.* Not "byte-exact across all ten".

### What this does and does not demonstrate

This run was executed **on the same host that produced the original
measurements**. It therefore demonstrates *build and environment
reproducibility* — the pinned image, the public inputs, and the recorded
commands regenerate the published numbers.

It does **not** yet demonstrate independent reproduction on third-party
hardware, which is what an outside reviewer should actually want. That is the
gap this package exists to close, and running it is the thing we are asking for.

### Verify the rar delta yourself

You do not have to take the explanation on trust. Compress one silesia file
with its extracted timestamp, then with a fresh one:

```sh
cp -p corpus/silesia/dickens ./a && cp corpus/silesia/dickens ./b && touch ./b
rar a -idq -y -m5 -ep a.rar a && rar a -idq -y -m5 -ep b.rar b
stat -c '%s %n' a.rar b.rar     # b.rar is 16 bytes larger
```

The same check on `canterbury/alice29.txt` gives 51,179 bytes with its 1996
timestamp and 51,195 with a recent one.

## Why rar is treated differently

Two reasons, and until 2026-07-30 we had only found one of them.

**Thread count — the larger effect, now pinned.** rar's compressed output is a
function of how many compression threads it uses, and rar 7.00 selects that from
the CPU count visible to it when no `-mt` flag is passed. This package used to
pass none, so **the same input produced a different archive on every
differently-sized host**. On `silesia/mr` the spread across `-mt1` … `-mt16` is
11,393 bytes; between 12 and 16 threads alone it is 5,716. That is what was
behind the long-unexplained 5,732-byte disagreement on that one cell, and it
meant this verifier would have rejected an honest third-party run on most
machines while blaming a timestamp for it.

Worse, that auto-detection cannot be contained from outside the process.
`strace` shows rar reading **`/sys/devices/system/cpu/online`** — the machine's
online CPU list — and never calling `sched_getaffinity`. So `taskset` does not
change its choice, and neither does a container CPU limit: `/sys` inside a
container still reports the host's CPUs, which means this package's own
`docker run --cpus=4` gave no protection at all.

`archiver_templates.json` now pins `-mt16`, which removes the auto-detection
path entirely. `-mt` demonstrably controls the output — sweeping `-mt1` … `-mt64`
on `silesia/mr` produces distinct, repeatable sizes spanning 11,393 bytes — and
16 is the value the frozen expectations in `expected_cells.json` were produced
at.

**Confirmed on two hosts of different size**, which is the only test that
actually settles it. Compressing `silesia/mr` with a normalised source
timestamp:

| host | online CPUs | `-mt16` pinned | no `-mt` |
|---|---|---|---|
| A | 16 | 2,781,302 | 2,781,302 |
| B | 64 | **2,781,302** | 2,779,962 |

Pinned, the two hosts agree to the byte. Unpinned, they disagree by 1,340 bytes
— and that is the smaller end of the effect; the same knob moves `silesia/mr` by
5,716 bytes between 12 and 16 threads.

A full 24-file, nine-archiver run on host B with `-mt16` pinned reproduced host
A's frozen expectations on **204 of 216 cells byte-for-byte**, all 216 round
trips exact. The twelve that differed were the twelve silesia rar cells,
uniformly −16 bytes — the timestamp effect below, not a compression difference.

**Timestamps — 16 bytes.** rar stores each source file's modification time and
widens that encoding for recent timestamps, so its archive size also depends on
how the corpus was copied rather than on content alone. It is the only one of
the ten archivers with that property — the other nine are byte-identical given
the same input.

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

> **If you skip this, the run dies with a bare `exit 3`.** Cubrim prompts for
> licence acceptance on first use and records the answer under `$HOME`. A
> container has no TTY and an ephemeral `$HOME`, so the prompt's stdin read
> fails with `Error: No such device or address (os error 6)` and the tool exits
> 3 on the very first Cubrim cell — with nothing in the journal pointing at a
> licence prompt as the cause.
>
> Our first attempt at this run (`cubr0069-20260728T173954Z`) died exactly that
> way. It is easy to miss on a machine where a developer once accepted the terms
> interactively, because the recorded acceptance then makes everything work
> locally while breaking in every container and CI job. Hence the explicit
> opt-in above rather than a silent auto-accept.

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
