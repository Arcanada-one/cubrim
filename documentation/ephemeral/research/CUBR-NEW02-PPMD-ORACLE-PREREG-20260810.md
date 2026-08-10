# NEW-02 canonical PPMd oracle-grid preregistration

Date: 2026-08-10
Status: prospective; must be committed on the exact execution revision before outcome access

## Prior evidence boundary

A detached two-prefix pilot exists. This registration does not read, reproduce,
summarize, or infer its outcomes. The pilot is not the canonical experiment and
cannot answer, modify, or stop the grid below. The ordered 27-file, 243-cell
canonical grid remains prospective.

## Frozen question and scope

NEW-02 asks how the external 7-Zip PPMd oracle behaves per file across a small,
fixed order/memory grid before any Cubrim implementation is compared with it.
This registration freezes measurement mechanics only. It contains no expected
result, aggregate, ranking, winner rule, or implementation-selection rule.

The canonical factors, in their execution order, are:

- PPMd order: `4`, `6`, `8`.
- Requested memory: `16`, `64`, `256` MiB.
- CPU affinity: exactly `0-15`.
- One invocation per file/order/memory cell: no retry and no averaging.
- Per-file observations only: no corpus-wide aggregate.

The canonical inventory has 27 entries in this cohort order: 11 `world`, 10
`tuned`, then 6 `holdout`. Its canonical tuple serialization is
SHA-256 `77b355f6b109acb26eb5606cf1538e2e6628fac3f6ed88b76f99f70a9716ceda`.
The ordered inventory names are:

1. `world`: `dickens`, `reymont`, `webster`, `xml`, `enwik8`,
   `alice29.txt`, `asyoulik.txt`, `cp.html`, `lcet10.txt`, `plrabn12.txt`,
   `xargs.1`.
2. `tuned`: `binary_mixed.bin`, `block_bound_runs.bin`,
   `both_sparse_16.bin`, `both_sparse_24.bin`, `dense.bin`, `log_like.bin`,
   `random_high.bin`, `sparse_clustered.bin`, `sparse_small.bin`, `text.bin`.
3. `holdout`: `rust_src.rs`, `c_header.h`, `config.json`, `prose.txt`,
   `data.csv`, `exe.bin`.

The nested loop is inventory entry, then order, then memory. It therefore has
exactly `27 * 3 * 3 = 243` cells. The canonical serialization of all 243 cell
identities, including inventory tuple, order, requested memory, and CPU set, is
SHA-256 `8c5f8d8ba6016f03eded06842d444a6ac06f417e6ae8fd01db9d0e0abef206f4`.
The companion harness contains the full sizes, relative paths, and SHA-256
values covered by these two frozen identities; every input must match before
the first child process runs.

`holdout/exe.bin` is not a runtime fallback. Before outcome access it is
explicitly materialized from the authenticated canonical `/bin/cat` bytes:
39,384 bytes, SHA-256
`a63158e6e5bce20616425f5d61e5bd7374bb5bccf15bbb93ae2e40238248f179`.

## Exact cell protocol

The encoder command shape is:

```text
/usr/bin/time -v -o ENCODE_TIME /usr/bin/taskset -c 0-15 \
  /usr/bin/7z a -t7z -m0=PPMd -mo=ORDER -mmem=MEMORYm -bd -y ARCHIVE INPUT
```

The decoder command shape is:

```text
/usr/bin/time -v -o DECODE_TIME /usr/bin/taskset -c 0-15 \
  /usr/bin/7z x -so -y ARCHIVE > DECODED
```

For each cell, the harness records charged archive bytes and SHA-256 plus
separate GNU-time elapsed seconds and peak RSS for encoding and decoding. It
then requires all of the following:

1. Encode, technical-listing, decode, and `cmp -s` each exit zero without an
   error marker.
2. `7z l -slt` describes exactly one member with the registered name and input
   size. Authoritative revalidation executes the provenance-authenticated,
   pinned 7-Zip binary with the canonical `l -slt` command against the actual
   manifested archive artifact. It parses that fresh stdout; row-supplied
   listing text is retained evidence but is never authoritative by itself.
3. That member's method is exactly `PPMD:oORDER:memE`, where `E` is the exact
   effective exponent reported by 7-Zip after its small-input cap. A generic
   archive-level PPMd header, a method chain, LZMA2, or a different order or
   exponent is a failure; there is no tolerance.
4. `cmp -s` succeeds and input/decoded SHA-256 values both equal the frozen
   input identity.

Every authoritative JSONL row has an exact, closed schema derived again from
its declared cell and authenticated provenance. Its encode, technical-listing,
decode, and `cmp` command arrays must equal the canonical tool paths and exact
operands. Input operands use the registered cohort-relative identity; archive,
decoded, and GNU-time operands use the exact publication-relative
`cells/CELL-SLUG/...` artifacts. The validator does not accept row-supplied
substitutions for a tool, switch, order, memory, input, archive, decoded file,
or comparison operand. It reparses the raw technical listing and requires the
recorded member method, order, effective memory exponent, name, and size to
agree exactly.

Elapsed values must be finite and nonnegative. RSS and all byte counts must be
integral and nonnegative (the charged archive is strictly positive). Each row
binds the exact regular input, archive, decoded, and timing artifacts by
relative path, size, and SHA-256. Published artifacts must match both the row
and the exhaustive manifest; input identity must match the registered source.
Each stored GNU-time artifact must also match the exact GNU `time -v` text
grammar: the complete recognized field set in canonical order, no duplicate
fields, exact numeric forms, and exactly one elapsed and peak-RSS field. The
validator parses both timing artifacts afresh and requires their elapsed/RSS
values to equal the respective
encode/decode row values exactly; a correctly rehashed timing drift is a
failure.
The row also repeats and must exactly match its run, code, inventory, grid,
tool, preregistration, and cell identities.

No failed cell is retried. Any setup, preflight, output, staging, publication,
or cell failure makes the attempted run `VOID` and creates no usable result.

## Provenance and publication authority

Before the first cell, the harness must authenticate:

- exact clean `HEAD`, equal to `origin/main`;
- this exact committed repository path and its pinned SHA-256/blob identity;
- exact harness and test bytes;
- the frozen inventory and grid identities;
- resolved `7z`, `taskset`, GNU `time`, and `cmp` paths, version-command output,
  and executable SHA-256 values;
- a recomputed run identity over all of the above.

Success publication is all-or-nothing: same-filesystem stage, exhaustive
manifest, file and directory `fsync`, hidden publishing rename, durable
`pending -> COMPLETE` marker transition, read-only tree, no-replace rename into
the preregistered final namespace, and parent-directory `fsync`. Only that
exact final namespace may be authoritative. A stage or hidden publishing tree
is never an authoritative result even if all bytes and markers are present.
An injected exception immediately after the final rename but before that
parent-directory `fsync` must atomically no-replace rename the visible final to
a unique hidden quarantine namespace and then `fsync` the parent before the
exception escapes. The quarantined tree is preserved for diagnosis but is not
authoritative and cannot validate as the registered final namespace.

A durable append-only JSONL VOID journal is the only failure publication. The
primary failure is journaled before cleanup; cleanup failure is also journaled
without erasing the primary record or its evidence path. The oracle writes no
measurement to a database, API, site, or backlog.

## Freeze rule

This file and the harness must land together before canonical-grid outcome
access. After that point, changing the inventory, order, memory, pin, commands,
verification, provenance, or publication rules requires a new prospective
registration and a new run identity. The detached pilot cannot be promoted or
backfilled into any of the 243 cells.
