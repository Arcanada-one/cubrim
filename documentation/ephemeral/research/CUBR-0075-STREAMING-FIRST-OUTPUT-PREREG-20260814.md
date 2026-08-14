# CUBR-0075 Streaming / First-Output Measurement — Preregistration

Status: frozen preregistration
Scope: internal CUBR-0075 streaming and first-output hypothesis
Date: 2026-08-14 UTC

This note freezes the measurement protocol. It reports no measured values and
makes no evaluation or production claim.

## Frozen corpus and implementation

- Corpus: `bench/web-corpus/manifest.v3.json`, schema version `2`, exactly 13
  samples, with the manifest byte counts and SHA-256 values authoritative.
- Frame producer: `cubrim::encode_with_config` with
  `EncodeConfig::web_profile=true` and a `65,536`-byte Web Profile block size.
- Decoder under test: the existing public `cubrim_web_decoder::StreamDecoder`
  API, which is the native implementation behind the browser/WASM surface.
- Input delivery: fixed `4,096`-byte pieces. Every piece is submitted before
  the next piece is delivered; no whole-frame input is available to the stream
  decoder before the loop reaches it.
- Output observation: each non-empty `StreamDecoder::push` window is handed to
  an independent digest sink immediately. A first-output event is the first
  such handoff, not a timestamp taken after a whole-buffer decode.
- Control mode: the same encoded frame is decoded with the whole-buffer
  `decode` function and handed to the same sink once. It is a control, not a
  streaming claim.

## Frozen trial protocol

- Cells: 13 samples × 2 modes (`streaming`, `whole_buffer`).
- Per cell: exactly 3 warmups followed by exactly 30 measured trials.
- Cell order: deterministic Fisher-Yates schedule with seed `75075`.
- Timing: monotonic `Instant`; record first input/output handoff, the input
  byte count at first output, last input submission, and final output handoff.
- Admission: one effective CPU, verified by the runner before and after the
  probe; load and temperature are recorded and a failed admission voids the
  run rather than entering a result.
- Integrity: every measured trial must finish successfully, match the original
  bytes exactly, and match the manifest SHA-256 at the sink. Missing, malformed,
  reordered, or non-finite event data is `VOID`.

## Frozen outcome rule

The run is a valid measurement only when all `13 × 2 × 30 = 780` measured
trials and all warmups have valid provenance and exact round trips. A streaming
trial is counted as first-output-before-EOF only when its first output input
byte count is strictly less than the encoded frame length. A complete and
integrity-valid trial that does not satisfy that predicate is a valid negative
observation, not a zero and not a missing row.

The aggregate result is `GO` only if every streaming measured trial has a
first-output-before-EOF event and the streaming median first-output input
fraction is strictly below `1.0`. Otherwise the valid aggregate is `NO_GO`.
If any protocol, provenance, admission, cardinality, or integrity invariant
fails, the aggregate is `VOID` and no threshold result is asserted.

## Non-claims and boundaries

This slice measures API-to-sink incremental behavior and its first-output
boundary. It does not claim independent-block decoding, throughput, ARM
silicon, bounded-state memory, database/API/site publication, production
readiness, or public/upstream release. A sequential multi-block stream is not
an independent-block container; this protocol makes no such inference.
