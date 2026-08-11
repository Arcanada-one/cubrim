# CUBR-0076 — step 2 prototype, preregistration of the corpus measurement

**Date:** 2026-08-11 UTC
**State:** the prototype exists (MODE_WEB, `code/cubrim-rs/src/web.rs`) and its
16 unit tests pass, but **it has not been run on the census corpus**. No
per-sample size, no aggregate, and no round-trip result on any of the 12
payloads has been produced or inspected at the time this document is committed.
**Registry identity:** extends hypothesis **13**. No duplicate row, no DB
write, `evaluation` stays 0.
**Predecessor:** [`CUBR-0076-SIZEMODEL-RESULTS-20260811.md`](CUBR-0076-SIZEMODEL-RESULTS-20260811.md)
(step 1, charged size model, GO-density in model at 121608 B).

## What was built

Step 2 of [`CUBR-0076-PROTOTYPE-SHAPE-20260806.md`](CUBR-0076-PROTOTYPE-SHAPE-20260806.md):
a prototype behind a scheme flag, encoder-side only, with byte-exact round trip
as the first gate.

- `MODE_WEB` (container byte 18): whole-file LZ parse coded with canonical
  Huffman tables transmitted in the block header and frozen for the block.
  Decode adapts nothing and runs through the repository's existing flat
  `HuffTable` lookup — the architecture class the web gate's decode budget
  admits.
- Opt-in via `EncodeConfig::web_profile` (default `false`) and competitively
  size-picked against the ordinary encoding, so default output is byte-identical
  to today's and no file can regress.
- Encoder carries the shortest-path parse the size model showed was decisive,
  and offers 1-context and 3-context literal tables, keeping the smaller.

Deliberate deviations from the Python size model, all of which cost bytes:

| deviation | direction | reason |
|---|---|---|
| code-length limit 14, not 15 | costs | reuses the repo's flat `HuffTable`, capped at 14 bits |
| frame header 14 B fixed, not LEB128 (~12 B) | costs ~2 B/file | matches the container conventions of MODE_LZ and friends |
| 18-bit hash chain, not an exact 3-byte dictionary | costs | bounded memory; hash collisions only lose candidates |
| contexts {1, 3}; the model also tried 2 | costs | 2 never won a file in the model |

## Falsifiable prediction (committed before the corpus is touched)

1. **Round trip: 12 of 12 byte-exact.** Anything less is a hard failure of the
   prototype, not a finding to be qualified.
2. **Aggregate between 119000 and 127000 B** — near the model's 121608 B, with
   the deviations above pushing slightly up.
3. **Still GO, still not WIN:** aggregate below the gzip-9 bar 129193 and above
   the brotli-11 bar 108495.
4. **MODE_WEB is selected on at least 11 of the 12 samples** under
   `web_profile = true`; woff2 is the one that may fall back, because its
   modelled margin over the incumbent was 26 bytes.
5. **Default output is unchanged:** with `web_profile = false`, `encode` is
   byte-identical to the pre-change encoder on every sample.

Any of these being wrong is recorded as wrong in the results document.

## Gates

- Byte-exact round trip through the **public** `decode` entry point (not a
  private helper) on every observation.
- The existing suite stays green: `cargo test --release` in full, including the
  `scheme_roundtrip` silent-data-loss gate that CI runs.
- Fail-closed decode is unit-tested for truncation, corruption, declared-length
  mismatch and checksum mismatch, and is asserted never to panic.
- `cargo fmt --check` clean (CI gate).

## Out of scope

Throughput of every kind. The prototype is not timed here, on this host or any
other; the decode-speed leg of hypothesis 12 stays a void until a quiet host
exists under the CUBR-0074 protocol. No claim about the archival lane, no site
or leaderboard change, no DB write.
