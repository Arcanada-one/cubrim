# CUBR-0074 Gate 2: reference-channel gate

**Status:** BLOCKED / VOID — the isolated reference channel is implemented, but the
required candidate run cannot produce a complete validated bundle because the
first required warmup times out on the large JSON sample.

## Gate

The existing 0074 corpus-parity criteria remain the ratio gate:

- `ratio_vs_brotli11 <= 1.00` is the continuation gate.
- `ratio_vs_brotli11 <= 0.92` is the stronger WIN gate.
- `real_world_sample_share >= 0.80` remains required.
- `decode_throughput_vs_brotli5 >= 0.50` is the fixed decode gate.
- Exact byte-for-byte round-trip is required for every resource in all measured cells.

The throughput factor is 0.50 because decoding is on the browser critical path. A
candidate must deliver at least half of Brotli-5's decode throughput, allowing at
most twice the decode latency of the dynamic-response baseline. This permits one
equal-sized decode-latency budget for a new codec while rejecting a four-times-slower
decoder that would not be a credible browser delivery path. Brotli-11 remains the
density baseline; Brotli-5 is the speed baseline actually used for dynamic web
responses.

## Reference-channel choice

Use a separate `reference_phase_a` channel for `cubrim-lowmem-decode`. It leaves the
published five-codec `PHASE_A_CODECS` tuple, its bundle verifier, and its existing
120 validated rows byte-identical. The candidate is explicitly archival and
whole-buffer: it is not normalized to `cubrim-web`, has no real Web Profile, and
must not be presented as a shipping web codec.

The reference channel will reuse the existing sample manifest, trial order,
30-trial/3-warmup protocol, subprocess sandbox, provenance, five metrics, exact
round-trip checks, and summary machinery. It will add no format, WASM, proxy,
Chromium, or standards work.

## Verification and measurement result

- Gate2 implementation commit: `f9176dcfc6ae7ee003486ae3ed4c67280fe55639`.
- Candidate binary: `cubrim 0.3.2`, SHA-256
  `b14aa4009d5bd3c277c9f7da792dbadec256c2c801da64c6b2064643fcedd1c1`.
- The required eight-sample `manifest.v1.json` was used; its manifest SHA-256 is
  `9a0fcb56b9af5c98cd987d1ad289f5adde4b073480646fb472d784b0bbf58599`.
- Focused attribution tests and the full Python harness passed: `51/51`.
- Full release Rust tests passed in a clean detached worktree: 311 library tests,
  7 CLI tests, 5 archive integration tests, 2/1/1 benchmark tests, and 10
  differential tests, with no failures.
- The deterministic canonical five-codec fixture bundle is byte-identical before
  and after the reference-channel change: SHA-256
  `5dcdd335d53c63a3be6a493cd07b4baebb7e963d83dbf96bbc091317a47a615f`.
- The reference run was launched with 3 warmups and 30 trials per cell under the
  unchanged 60-second subprocess timeout. Both attempts journaled the same first
  failure: `json-api-large-v1/cubrim-lowmem-decode`, warmup `-1`, reason
  `timeout`. The quiet-host recovery attempt was admitted at load-per-CPU `0.390`,
  so the repeat is an intrinsic protocol timeout, not an admission rejection.
- No candidate bundle, summary, evaluation, evidence, or derived row was written.
  The authoritative DB remains at one validated baseline run, with criterion 57
  set to `decode_throughput_vs_brotli5 >= 0.50` and dependency 5 still
  `pending_dependency`.
- Candidate build 7 remains immutable and still advertises
  `hostile_input_hardened=false`, `roundtrip_exact=false`, and no Web Profile;
  it was not mutated or used to manufacture a passing evaluation.

## Stop conditions

- If any existing five-codec bundle or summary changes, stop and treat it as a
  published-result regression.
- If any candidate resource fails exact round-trip, do not write numeric evaluation
  rows; retain only a journaled void.
- Do not resolve the 0074 dependency or write evaluation/evidence/derived rows until
  every candidate cell is complete and validated.
