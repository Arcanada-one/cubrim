# Changelog

All notable changes to the Cubrim compressor and CLI are recorded here.
Ratios quoted below are measured on the frozen benchmark corpus with the
binary built from this revision — never estimated.

## [0.3.0] — 2026-07-23

First consolidated release candidate: three independently developed, orthogonal
work streams merged onto a single champion base, plus two defects found and
fixed while proving the merge.

### Added

- **`MODE_GEOCM` (17) — geometric image codec** offered as a competitive-min
  candidate. Measured image-type aggregate **0.302670** (ptt5 0.057397,
  x-ray 0.429187, mr 0.207765), byte-exact round-trip on all three.
- **`MODE_MED16` context bias-cancellation (APM) variant**, selected
  competitively. The APM flag is packed into the high bit of the width field,
  so the container is unchanged for the non-APM path.
- **`MODE_RECORDCM` per-offset SSE variant**, competed against the plain
  record-CM candidate. Measured sao **0.525384**. The SSE flag is carried in
  bit 15 of the record-width field.

### Security

Fail-closed decode hardening against corrupt/hostile archives. Attacker-controlled
header values (declared length, element counts, table indices) previously drove
unbounded allocation, unbounded decode loops, or out-of-bounds panics instead of
a clean error. All six defects now fail closed in bounded time and memory:

- `MODE_CM2`: a declared output length up to 2^64 drove an unbounded decode loop
  (>30 s, multi-GB). Now capped by an absolute maximum plus a stall detector.
- `MODE_CM`: unchecked block size drove a multi-hundred-GB allocation. Now
  requires the canonical block size and a checked allocation.
- `MODE_CUBE`: an inflated element count drove a multi-GB allocation. Now bounded
  by cube capacity and an absolute maximum.
- `MODE_LZ`: an unchecked match count drove a multi-GB allocation. Now enforces
  the count <= token count <= output length invariant.
- Nested helper decoders (bit-packing, run-length, Huffman): uncapped
  preallocation. Now capped.
- `MODE_CUBE` entropy decoders: an attacker-supplied table index into an empty
  table set caused an out-of-bounds panic. Now bounds-checked.

Preallocation caps are hints only — decoded output is byte-identical for every
valid archive, and the guards only enforce invariants that hold for all of them.

### Fixed

- **The `MODE_CM2` stall detector could never fire.** It compared the range
  decoder's input position across output bytes, but that position advances
  unconditionally while the decoder reads zero-padding past the end of the coded
  stream — so the "no progress" condition was unreachable. A truncated stream
  claiming 1 GiB decoded a fabricated 1 GiB successfully instead of erroring.
  The progress counter now saturates at the end of the real coded stream.
  Valid round-trips are unaffected, including maximally-compressible inputs
  whose decoder rides closest to the end of input.

### Changed

- The fixed-record selection test no longer asserts which candidate wins the
  default competition. On a smooth 2-D fixture the geometric codec legitimately
  out-compresses record-CM and wins competitive-min. The test now asserts the
  stronger and stable properties: the record-CM candidate is live in the
  competition, competitive-min never selects a candidate larger than it, and the
  winner round-trips byte-exactly.
