# FU-01 — large-BWT design

## Decision

Use a new self-describing top-level `MODE_LARGEBWT = 11`. Do not widen the
existing two-byte BWT fields in place: all current cube value schemes and their
decoders depend on that exact v1 wire. Do not version the whole cube format:
FU-01 needs one additive candidate, not a second copy of every existing mode.

The existing operator-approved FU-01 checkpoint remains authoritative:
`plrabn12.txt <= 0.33` on real bytes, with RT=OK/cmp=0. Failure moves priority
to IW-04/NEW-02 instead of adding more BWT complexity.

## Alternatives considered

1. Widen every existing BWT value-scheme primary index from u16 to u32.
   Rejected because old v1 blobs become ambiguous and new decoders could no
   longer distinguish two-byte from four-byte payloads.
2. Introduce format version 2 for cube, raw and every container mode. Rejected
   because the migration and compatibility surface is much larger than the
   hypothesis.
3. Add one top-level large-BWT mode. Selected because old modes remain
   byte-identical and the new decoder has an unambiguous dispatch byte.

## Wire format

All integers are big-endian.

```text
[MAGIC 4B = CB 52 49 4D][VERSION 1B = 1][MODE 1B = 11]
[orig_len u64][block_size u32][n_blocks u32]
n_blocks * [raw_len u32][primary_index u32][comp_len u32][raw_hash64 u64]
concatenated order-1-rANS payloads
```

Each payload is the order-1-rANS encoding of one complete raw-byte BWT block,
with alphabet size 256. The BWT primary index is charged once per block. The
table is validated before allocation: block size and count must be non-zero,
raw lengths must sum exactly to `orig_len`, compressed lengths must sum exactly
to the remaining payload, every primary index must be below its raw length, and
all arithmetic is checked. The existing deterministic `cm_hash64` primitive is
reused for byte-exact block integrity; no new checksum dependency is added.

Candidate block sizes for the spike are 256 KiB and 1 MiB. A final short block
is legal. This first stage does not claim 4 MiB feasibility; that requires
measured SA-IS memory/time evidence on dev-ai.

## Code boundaries

- Generalize the internal BWT core to return/accept `usize` primary indexes.
- Preserve current `bwt_encode_codes(...)->u16` and
  `bwt_decode_codes(..., u16, ...)` as checked wrappers so every existing value
  scheme emits and reads exactly the old bytes.
- Add private u32 large-BWT encode/decode helpers used only by mode 11.
- Add mode-11 dispatch before `parse_header`, matching other top-level modes.
- Keep the candidate behind strict competitive-min. The first spike may expose
  forced helpers/tests, but it does not enter the default rail until full-24
  verification.

For production eligibility, reuse the existing CM text-likeness detector rather
than inventing a second classifier. Non-text data does not pay the BWT probe.
During research, forced measurement is allowed and must be labelled forced.

## Failure handling

Decoder errors are explicit for truncated headers/tables, impossible block
counts, out-of-range primary indexes, rANS length mismatch, payload overflow,
and hash mismatch. No partial plaintext is returned. Existing v1 decoding is
covered by differential tests and must remain byte-identical.

## Verification

1. Unit/property tests: u32 BWT round trips at 65,535, 65,536, 65,537, 256 KiB
   and periodic/adversarial inputs; malformed table/primary/hash cases.
2. Compatibility: existing focused BWT tests and differential fixtures retain
   exact output bytes.
3. dev-ai spike, sequential and `CUBR_THREADS=4`: forced 256 KiB and 1 MiB on
   `plrabn12`, `alice29`, `asyoulik`, `webster`; exact compressed bytes, ratio,
   wall time, peak RSS, RT=OK and cmp=0.
4. Falsification: if the best charged candidate does not make
   `plrabn12 <= 0.33`, stop FU-01 and prioritize IW-04/NEW-02.
5. Only after the checkpoint passes: full 24-file competitive-min run and rank
   recalculation. Zero per-file regression is structural because a mode-11 blob
   is selected only when strictly smaller.

## Scope boundary

FU-01 does not promise to beat PPMd by itself. It tests whether the current
BWT+rANS backend recovers enough cross-block context to justify a larger block.
PPMd parity, word models, cross-block adaptive statistics and 4 MiB tuning stay
in their existing hypotheses.
