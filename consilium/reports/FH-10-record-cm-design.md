# FH-10 record-aware CM forced probe

**Status:** design for a private, non-default experiment. No measured result yet.

## Question

Can a context mixer that preserves raw record order close the remaining `sao`
gap to the binary leader? Existing `MODE_SOA` exposes vertical byte columns but
breaks horizontal within-record locality. FH-10 instead keeps every byte in its
original position and adds record-coordinate evidence to CM.

## Isolated mechanism

- Add the free additive top-level `MODE_RECORDCM=13`. It is decoded by the
  library but is absent from every production encoder dispatch path.
- A private `encode_record_cm_probe` calls existing `soa_detect_width`; the real
  `sao` probe must detect exactly `W=28` or fail before emitting a result.
- Reuse the existing CM arithmetic coder, base order-0..6/word/match models,
  block table, per-block raw hash, and exact length checks.
- Only record-mode predictor instances add two mixer inputs:
  1. `byte_position % W`, combined with the current partial-byte prefix;
  2. the previous byte at the same record offset (`position-W`), combined with
     the offset and partial-byte prefix. The first record has an explicit
     no-previous-record context.
- Use `% W`, never a power-of-two mask: the target width is 28.
- Raw bytes are not transposed or otherwise transformed. Decoder state follows
  exactly the same online observations as encoder state.
- Ordinary `CmPredictor::new()`, `MODE_CM`, `encode_bcj`, and the default
  dispatcher retain their existing calculations and wire bytes. Record state
  exists only in `CmPredictor::new_record(width, block_start)`.

## Wire

```text
MAGIC[4] VERSION MODE_RECORDCM
orig_len:u64 block_size:u32 n_blocks:u32 width:u16
n_blocks * (comp_len:u32 raw_hash64:u64)
concatenated range-coded blocks
```

The width is restricted to `4..=64`. Every decoded block is checked against its
declared length and hash; final reconstructed length must equal `orig_len`.
Block predictors receive the raw block start offset so `position % W` remains
correct when a file spans multiple CM blocks. The first W bytes of each block
use the explicit no-previous-record context.

## Verification

Local deterministic tests:

1. Synthetic 28-byte fixed-record stream is detected as W=28 and round-trips
   through `MODE_RECORDCM`.
2. Existing direct `MODE_CM` round-trip/checksum tests remain green.
3. Truncated header/table/payload, invalid width, bad block length, and corrupt
   hash are rejected.
4. `cargo fmt --check`, `cargo check --lib`, focused CM tests, and
   `git diff --check` pass before bundling.

The ignored real-corpus test runs only on dev-ai after the existing queue and
the three-minute `load<12`, `paxbt=0`, Cubrim-idle gate. It uses
`CUBR_THREADS=4` and the exact full Silesia `sao` path, then records:

- input size and SHA256 outside the test;
- exact current top-level rail and forced record-CM archive sizes, modes,
  ratios, elapsed times, and byte-exact decode;
- fresh `xz -9e`, `7z -t7z -m0=LZMA2 -mx=9`, and `rar a -m5 -ep` archive
  sizes with extraction and `cmp=0`.

## Decision gates

- **GO-to-full-24:** record-CM beats the exact current rail on `sao` by at
  least 1.5% and RT/cmp is clean. Beating the fresh external leader is reported
  separately; it is not assumed.
- **NO-GO:** no 1.5% self-gain, detector does not return 28, or any correctness
  check fails.
- A binary aggregate computed before full-24 is labelled projection only and
  uses exact original-byte weighting. No database mutation and no default-rail
  integration occur before real full-24 numbers.
