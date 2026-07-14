# Cubrim-1 leader-gap literature resolution

**Status:** existing-card resolution. The ideas below map to canonical OPEN/IN-WORK
cards already present in the database. No new IDs are allocated, and no codec or
database change is implied by this report.

## Measured gap that defines the wave

The current complete 24-file world benchmark (`CUBR-0043-full24-cm19-p27b-corrected`)
puts Cubrim first overall at `0.22270749319769523`, but three type aggregates still
lose:

| type | Cubrim | leader | leader ratio | gap |
|---|---:|---|---:|---:|
| text | 0.21265653738950635 | ppmd | 0.2013791444312253 | +5.60% |
| binary | 0.5541517791480888 | 7z | 0.5377525162660062 | +3.05% |
| exe | 0.29355779350869265 | 7z | 0.2748738268008853 | +6.80% |

The binary label hides two unrelated files: `kennedy.xls` is a BIFF spreadsheet,
while `sum` is a SPARC executable according to the Canterbury corpus. The wave
therefore attacks physical structure, not the coarse benchmark label.

## Primary literature and specifications

- Dmitry Shkarin, "Improving the Efficiency of the PPM Algorithm" (2001),
  DOI `10.1023/A:1013878007506`: generalized symbol and escape frequencies are
  the basis for genuine PPMd-class efficiency.
  <https://www.mathnet.ru/eng/ppi526>
- 7-Zip LZMA SDK: public-domain reference code; current SDK explicitly includes
  improved BCJ2 plus ARM64 and RISC-V filters.
  <https://www.7-zip.com/sdk.html>
- XZ/liblzma BCJ API: architecture-specific filters are size-preserving; its
  `start_offset` exists specifically for separately filtered executable sections
  with cross-section branches.
  <https://chromium.googlesource.com/chromium/deps/xz/+/refs/heads/main/src/liblzma/api/lzma/bcj.h>
- Microsoft `[MS-XLS]`: canonical Excel 97-2003 binary format specification.
  <https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/cd03cb5f-ca02-4934-a391-bb674cb8aa06>
- Canterbury corpus descriptions: `kennedy.xls` is an Excel spreadsheet and
  `sum` is a SPARC executable, despite both being grouped as `binary` in the
  current Cubrim benchmark.
  <https://corpus.canterbury.ac.nz/descriptions/>

## NEW-09 + NEW-10 - PE section-aware BCJ2 split streams

**Statement.** If x86 call/jump targets and the remaining executable bytes are
split into separately coded streams, with PE section virtual addresses charged
as decoder metadata, then the transform should recover the residual gap left by
the shipped single-stream x86 BCJ and beat the 7z exe aggregate.

**Mechanism.** H-45 proved that one-stream E8/E9 normalization is non-subsumed on
dense PE code. BCJ2 goes further: it separates branch/control information so the
target stream and ordinary byte stream can receive different probability models.
Parse PE sections, preserve every byte outside executable sections, and use each
section's virtual offset when normalizing cross-section targets.

**Pre-registered test.** `ooffice` and `mozilla`, then the full 24-file corpus.
Compare current rail, one-stream BCJ, BCJ2+current backend, and 7z. Charge mode,
section table, stream lengths, targets, and checksums. Require RT=OK/cmp=0.

**GO gate.** Exe aggregate `< 0.2748738268008853` and no selected-file regression
outside detected PE input. **NO-GO gate:** BCJ2 fails to improve one-stream BCJ by
at least 1.5% on `ooffice`, or charged metadata consumes the gain.

## IW-05 - SPARC BCJ for Canterbury `sum`

**Statement.** If `sum` is routed through a reversible SPARC branch converter
before the existing competitive backend, its current `0.275679916318` ratio should
fall below xz's `0.24843`, moving the binary aggregate toward the 7z leader.

**Mechanism.** The corpus source identifies `sum` as a SPARC executable. XZ and
7-Zip expose a SPARC BCJ filter, while Cubrim currently treats this file as generic
binary. Normalize only valid aligned SPARC control-transfer instructions and keep
the filter behind `min(raw, transformed)`.

**Pre-registered test.** Full `sum`, not a code slice; current rail vs Cubrim SPARC
BCJ vs `xz --sparc` where available. Include wrong-architecture controls (x86 and
ARM64 filters) and charge mode/header bytes. Require RT=OK/cmp=0.

**GO gate.** `sum < 0.24843` and full-24 binary aggregate improves. **NO-GO gate:**
charged gain is below 1.5% or an architecture control performs equally well.

## NEW-11 + FU-03 - OLE/BIFF record-stream decomposition for `kennedy.xls`

**Statement.** If the OLE Compound File container and BIFF workbook records are
parsed reversibly, then record ids, lengths, repeated cell metadata, and payloads
can be coded as separate streams; this may close the twofold gap between Cubrim
`0.06951824919591665` and rar `0.034542` on `kennedy.xls`.

**Mechanism.** `[MS-XLS]` defines a record-oriented workbook stream. A lossless
front end should preserve the complete OLE directory/FAT and all unknown records,
while separating only validated BIFF `(record_id, length, payload)` tuples. Candidate
substreams are record ids, lengths, row/column indexes, numeric payloads, strings,
and untouched residual records. Every stream length and exception is charged.

**Pre-registered test.** Parse and reconstruct `kennedy.xls` byte-exact before
compression. Measure raw rail, OLE stream split, BIFF tuple split, and field-aware
split through the same backend. Add malformed/truncated and unknown-record RT tests.

**GO gate.** Beat `0.034542` on the full file and improve the full-24 binary
aggregate without selecting on unrelated data. **NO-GO gate:** a byte-exact parser
cannot cover at least 95% of workbook bytes, or total charged output remains
`>= 0.034542`.

## NEW-02 + IW-04 - measured PPMd order/memory selector

**Statement.** A genuine PPMd implementation with per-file competitive selection
over a small pre-registered order/memory grid should reduce the text aggregate
below `0.2013791444312253`, while leaving CM-winning and transformed classes on
their existing modes.

**Mechanism.** This is the implementation-resolution card for H-61, not a naive
order-N retry. It requires PPMd escape handling and SEE-style estimation from the
Shkarin family. First use the public-domain 7-Zip implementation as an oracle to
measure orders `{4,6,8}` and memory `{16,64,256} MiB`; implement only the smallest
configuration that clears the world-text gate. Selection metadata and model memory
limits are part of the cost.

**Pre-registered test.** All 11 world-text files plus current tuned/holdout corpora.
Record exact order, memory, archive bytes, encode/decode time, peak RSS, RT, and
code SHA. Compare against current competitive rail and the published ppmd baseline.

**GO gate.** Full-24 text aggregate `< 0.2013791444312253`, RT=OK/cmp=0 on every
file, and no output regression because selection stays behind competitive min.
**NO-GO gate:** the 7-Zip oracle grid itself cannot clear the aggregate, or the Rust
implementation misses the oracle by more than 2% after format overhead.

## Execution order

1. IW-05: smallest end-to-end experiment and a correction to physical file typing.
2. NEW-09/10: extends an already measured x86 BCJ win and targets the entire exe gap.
3. NEW-02/IW-04 oracle grid: establishes the minimum genuine PPMd configuration before a
   multi-day implementation.
4. NEW-11/FU-03: highest possible binary payoff, but also the largest parser/RT surface.

All heavy runs are sequential on dev-ai with `CUBR_THREADS=4` and a load gate.
Database writes require a verified backup. Only measured full-24 results may enter
the evolution graph.
