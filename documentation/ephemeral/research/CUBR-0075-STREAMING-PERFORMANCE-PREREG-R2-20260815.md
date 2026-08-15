# CUBR-0075 Streaming / Early-Output Performance — Publication Rerun Preregistration

Status: frozen rerun preregistration  
Scope: internal native Web Profile measurement for `streaming-early-output-performance`  
Date: 2026-08-15 UTC

This rerun keeps the original CUBR-0075 matrix, thresholds, corpus, capability
controls, and NO_GO decision rule. It adds only the source-derived encoding
duration required by the canonical `resource_codec` evidence contract. The
original measurement and its result remain separate evidence; this rerun is
the publication-compatible bundle.

## Fixed implementation and corpus

- Source commit: `3d8d227`.
- Corpus: `bench/web-corpus/manifest.v3.json`, exactly 13 samples, reused with
  the original manifest SHA-256.
- Frame producer: `cubrim::encode_with_config` with
  `EncodeConfig::web_profile=true` and a `65,536`-byte Web Profile block size.
- Decoder: the existing native `cubrim_web_decoder` handle ABI.
- Input pieces: exactly `4,096` bytes, except the final shorter piece.

## Fixed trial protocol

- Cells: 13 samples × `streaming` and `whole_buffer` control.
- Each cell has exactly 3 warmups followed by exactly 30 measured trials.
- Cell order is deterministic Fisher-Yates with seed `75075`.
- For each sample/configuration pair, the probe performs exactly one fresh
  encode with the fixed Web Profile configuration, verifies the resulting
  frame length and SHA-256 against the preloaded frame, and records positive
  monotonic `compression_duration_ns`. That source-derived duration is
  attached to every streaming and whole-buffer row for that sample. Repeated
  rows are decoder observations only; they are not independent encode-timing
  replicates.
- The decoder observations use the verified preloaded frame. Their decode
  timers start after the encoding measurement, so encoding time is not included
  in decoder timings.
- Each decode timer records first output input bytes, first-output latency,
  last input submission, completion latency, peak ABI memory usage, and exact
  sink bytes/hash.
- The conservative streaming memory bound remains
  `max(cbm_stream_memory_usage) - frame_bytes - declared_output_bytes`,
  divided by `frame_bytes`.

## Publication mapping

The guarded API writer must preserve the eight canonical per-resource metrics:

| Metric | Source |
|---|---|
| `compressed_bytes` | `frame_bytes` |
| `compression_ratio` | `frame_bytes / input_bytes` |
| `compression_duration` | `compression_duration_ns / 1e6` |
| `decompression_duration` | `output_complete_latency_ns / 1e6` |
| `peak_memory` | `decoder_retained_peak_bytes` |
| `time_to_first_decoded_byte` | `first_output_latency_ns / 1e6` |
| `first_output_after_input_bytes` | `first_output_input_bytes` |
| `auxiliary_memory_bound_ratio` | bundle-derived ratio |

Missing, zero, non-finite, or frame-digest-drifting encoding timing voids the
bundle. No sentinel or inferred compression value is accepted. The existing
numeric thresholds and explicit independent-block capability criterion remain
unchanged; the expected decision remains `NO_GO`.

This is internal native ABI-to-sink evidence only. It does not claim browser
transport, process RSS, ARM, production, or public/upstream readiness.
