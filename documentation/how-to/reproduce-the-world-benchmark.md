# Reproduce the world benchmark

The published Cubrim world ratio benchmark can be reproduced independently. The
package that does it lives in [`reproducibility/`](../../reproducibility/) and
fetches everything it needs from public sources — corpora, the released Cubrim
binary, and the competing archivers — verifying each against a recorded
checksum.

See [`reproducibility/README.md`](../../reproducibility/README.md) for the full
procedure. In outline:

```sh
cd reproducibility
sudo docker build --platform linux/amd64 -t cubrim-reproducer:latest .
install -d -m 0700 "$PWD/workspace"

sudo docker run --rm -v "$PWD/workspace:/workspace" cubrim-reproducer:latest acquire
sudo docker run --rm --memory=32g --cpus=4 -e CUBRIM_ACCEPT_LICENSE=1 \
  -v "$PWD/workspace:/workspace" cubrim-reproducer:latest run
sudo docker run --rm -v "$PWD/workspace:/workspace" cubrim-reproducer:latest verify \
  --journal /workspace/results/RUN.journal.jsonl \
  --sidecar /workspace/results/RUN.journal.sha256.json
```

Budget several hours and 32 GiB of memory; the Cubrim phase dominates.

## What a pass means

All 240 file/archiver cells must compress, decompress, and pass an external
byte comparison. Nine of the ten archivers are additionally held to exact
archive sizes — 216 cells, including every Cubrim cell.

rar is the exception, and deliberately so: it stores each source file's
modification time and widens that encoding for recent timestamps, so its
archive size depends on how the corpus was copied rather than on content. It is
held to its round trip plus a 256-byte bound, and every difference is printed
and counted rather than absorbed.

The honest summary of our own reference run is that **nine of ten archivers
reproduce byte-for-byte, including every Cubrim cell; rar reproduces exactly
wherever corpus timestamps survive and to within its mtime header elsewhere.**

## If it does not reproduce

Report it with the raw journal and sidecar, unedited. A mismatch is the most
useful result this package can produce.
