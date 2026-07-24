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
- **BCJ branch-conversion composed with the CM2 backend** as a competitive-min
  candidate for executables: architecture detection selects the branch filter,
  whose output is then coded by CM2 and nested in the existing `MODE_BCJ`
  container. The wire format and the decoder are unchanged. Measured ooffice
  **0.286639** (1763460 B, down from 1991681 B), moving the executable-type
  aggregate to **0.244212**. Inputs with no detected architecture are untouched —
  mozilla is byte-identical at 12247649 B, the candidate simply does not fire.

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

- `MODE_CM2` expansion bound, enforced **before** any allocation: a declared output
  length must be plausible for the number of coded bytes actually present
  (`orig_len <= coded_len * 10000 + 65536`). The factor is calibrated against
  measured encoder output — the worst real compression ratios asymptote near 2400x,
  leaving more than 4x headroom — and a calibration test asserts the encoder stays
  more than 2x clear of the bound, so a future model change fails loudly instead of
  silently narrowing the margin. A 214-byte hostile archive that previously drove
  6.3 GB of resident memory over more than a minute is now rejected in 0.00 s at
  3.9 MB.

- **`MODE_GEOCM` expansion bound**, enforced ahead of every dispatch. The image
  codec is a separate module and so sat outside the `MODE_CM2` bound above: its
  declared length sized both the output vector and the model tables before any
  content was validated. The factor is calibrated the same way, against a measured
  worst ratio of 2752x. A 68-byte hostile archive is now rejected in 0.00 s at
  3.9 MB, and its range decoder gained the same saturating progress counter and
  stall detector.
- **Container nesting depth limit (32).** Modes that wrap a nested sub-blob could
  be chained by a crafted archive until the decoder exhausted the stack and the
  process died on a signal rather than returning an error. A depth counter inside
  `decode` now covers every recursive path at once: a 451-byte archive nesting 40
  branch-filter containers returns a clean error instead of crashing, while the
  legitimate two-level nesting the executable path relies on is unaffected.

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
