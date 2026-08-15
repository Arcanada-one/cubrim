# CUBR-0075 Streaming / Early-Output Performance — Preregistration

Status: frozen preregistration  
Scope: internal native Web Profile measurement for `streaming-early-output-performance`  
Date: 2026-08-15 UTC

This note freezes a bounded native measurement. It makes no database, site,
production, ARM, browser-paint, or public/upstream claim. It does not amend
the separate first-output preregistration.

## Fixed implementation and corpus

- Corpus: `bench/web-corpus/manifest.v3.json`, schema version `2`, exactly 13
  samples. The manifest SHA-256 is
  `43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5`.
- Frame producer: `cubrim::encode_with_config` with
  `EncodeConfig::web_profile=true` and a `65,536`-byte Web Profile block size.
- Decoder: the existing native `cubrim_web_decoder` handle ABI. Each input
  piece is submitted to one fresh stream and every non-empty ABI fresh window
  is copied immediately to an independent SHA-256 sink.
- Input pieces: exactly `4,096` bytes, except the final shorter piece.
- The memory metric is a conservative ABI-capacity bound, not RSS:
  `max(cbm_stream_memory_usage) - frame_bytes - declared_output_bytes`,
  divided by `frame_bytes`. A negative subtraction is a protocol failure.

## Fixed trial protocol

- Cells: 13 samples × `streaming` and `whole_buffer` control.
- Each cell has exactly 3 warmups followed by exactly 30 measured trials.
- Cell order is deterministic Fisher-Yates with seed `75075`.
- Timing uses monotonic `Instant`; each streaming trial records first output
  input bytes, first-output latency, last input submission, completion latency,
  peak ABI memory usage, and exact sink bytes/hash.
- The whole-buffer control is decoded with `cubrim::decode` and is not
  treated as incremental output.
- Runner admission requires one effective CPU, load per logical CPU ≤ 1.0,
  and every observed temperature strictly below 90°C, before and after the
  probe. A failed admission voids the run.

## Independent-block capability probe

The Web Profile decoder is ordered: a later block may use output retained from
predecessor blocks. Sequential multi-block output is therefore not independent
block decoding. The bundle includes an explicit capability observation with
positive and negative controls. `independent_block_decode_success` is true
only if a later block is decoded by a fresh decoder without predecessor output
and the reconstructed bytes and checksums are exact. The current v1 format has
no such operation, so the expected observation is false and must be published
as a measured `NO_GO` criterion, never inferred from ordinary streaming
success.

## Outcome rule

The run is valid only when all 780 measured trials and all warmups have exact
round trips, exact sink hashes, complete provenance, and finite ordered event
data. Missing output is not coerced to zero. Protocol, provenance, admission,
cardinality, or integrity failure is `VOID` and has no evaluation.

For a valid run, the derived values are the maximum measured
`first_output_after_input_bytes` and maximum
`auxiliary_memory_bound_ratio` over streaming measured trials. The evaluation
is `GO` only when the first value is ≤ 65,536 bytes, the second is ≤ 1.0, and
the explicit independent-block capability is true. Otherwise the valid result
is `NO_GO`. The expected current-format result is therefore `NO_GO` because
standalone predecessor-free block decode is not supported, even if the two
numeric measurements pass.

## Non-claims

This protocol does not measure browser or HTTP transport timing, visual paint,
ARM silicon, total process RSS, decoder redesign, public release readiness, or
the unrelated frozen first-output result. It also does not authorize a write
until the bundle is independently schema-validated and the guarded writer
rechecks the live dependency and protected-table fingerprints.
