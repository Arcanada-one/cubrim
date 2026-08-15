# CUBR-0075 Streaming / Early-Output Performance — Result

Status: **valid measurement — NO_GO**  
Scope: Cubrim native ABI-to-sink evidence for `streaming-early-output-performance`  
Date: 2026-08-15 UTC

## Decision

The frozen 13-sample × 2-mode matrix completed with exact round trips and
exact sink SHA-256 values for all `780` measured trials. The numeric
first-output bound passed (`23,650` bytes ≤ `65,536`), but the conservative
auxiliary-capacity bound failed (`681.9358151476251` > `1.0`) and the explicit
predecessor-free independent-block capability was false. The valid result is
therefore **NO_GO**.

This is a native decoder-capacity and API-to-sink result. It is not a browser
paint, HTTP transport, total-process RSS, ARM, or public-release result.

## Frozen protocol and evidence

- Preregistration:
  `CUBR-0075-STREAMING-PERFORMANCE-PREREG-20260815.md`; SHA-256
  `ac068fcfdb006d3401994d506d3f6c55f5588a0498a59dff8d735fcbe0b3083b`.
- Corpus: `cubr0074-web-real-v3`, 13 samples; manifest SHA-256
  `43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5`.
- Matrix: 13 samples × (`streaming`, `whole_buffer`) × 3 warmups × 30
  measured trials; seed `75075`; block size `65,536`; input pieces `4,096`.
- Bundle:
  `/home/dev/evidence/CUBR-0075-STREAMING-PERFORMANCE-20260815/streaming-performance.json`;
  SHA-256
  `b8493a33a3ee603cfce89799c99849abb7203e7c86d8b6953b1bdfb76ec9f4c2`.
- Bundle status: `COMPLETE`; streaming measured trials `390`; whole-buffer
  controls `390`; round-trip failures `0`.

## Provenance and admission

- Cubrim source commit: `fb89f8ad25aaab9b50510f4ffa3354983951eca6`.
- Probe binary SHA-256:
  `3438208c44a25fef5090e8b2cf55643db3efcbe621adaae94c203fa5b1a0c800`.
- Runner SHA-256:
  `a2a234fa0833f58cd0439b56b01779ede885907cb9fbed6761bad7c498068051`.
- Host: `arcana-devs`, `x86_64`, CPU affinity `0`, 16 logical CPUs,
  `rustc 1.97.1 (8bab26f4f 2026-07-14)`.
- Admission load per logical CPU: `0.21368408203125` before and
  `0.21661376953125` after. Temperatures remained below the strict 90°C bar.

## Aggregate measurements

| Criterion | Observed | Preregistered bar | Result |
|---|---:|---:|---|
| Maximum first output after input | 23,650 bytes | ≤ 65,536 bytes | GO |
| Maximum auxiliary capacity ratio | 681.9358151476251 | ≤ 1.0 | NO_GO |
| Independent block decode | false | exact boolean true | NO_GO |

The auxiliary ratio is the preregistered ABI-capacity calculation:
`max(cbm_stream_memory_usage) - frame_bytes - declared_output_bytes`, divided
by `frame_bytes`. It is not an RSS measurement.

## Per-sample streaming result

Each row contains 30 measured streaming trials. `Pre-EOF` counts strict
first-output events before the encoded frame ended.

| Sample | Pre-EOF | Max first input bytes | Max auxiliary ratio | Frame bytes |
|---|---:|---:|---:|---:|
| `css-medium-tailwind-v2` | 0/30 | 10,361 | 107.502461 | 10,361 |
| `html-large-web-codec-v2` | 30/30 | 8,192 | 79.239828 | 14,452 |
| `html-medium-home-v2` | 0/30 | 5,563 | 192.990653 | 5,563 |
| `javascript-medium-magic-string-v2` | 0/30 | 9,375 | 116.427947 | 9,375 |
| `javascript-medium-sourcemap-codec-v2` | 0/30 | 3,522 | 301.864281 | 3,522 |
| `javascript-small-resolve-uri-v2` | 0/30 | 2,797 | 378.420450 | 2,797 |
| `json-api-large-world-benchmark-v2` | 30/30 | 4,096 | 63.411223 | 18,445 |
| `json-api-medium-web-benchmark-v2` | 30/30 | 8,192 | 117.115239 | 9,502 |
| `json-api-small-hypotheses-v2` | 0/30 | 1,558 | 681.935815 | 1,558 |
| `source-map-large-magic-string-v2` | 30/30 | 16,384 | 58.685708 | 18,941 |
| `source-map-small-sourcemap-codec-v2` | 0/30 | 2,407 | 439.665974 | 2,407 |
| `wasm-medium-cubrim-decoder-v3` | 0/30 | 20,551 | 53.720354 | 20,551 |
| `woff2-medium-inter-latin-v20` | 0/30 | 23,650 | 45.337844 | 23,650 |

## Independent-block boundary

The positive control decoded the complete ordered frame exactly. The negative
control fed a frame suffix without the container header to a fresh decoder and
observed rejection. Combined with the current decoder's predecessor-retaining
ordered-block semantics, this is an explicit false capability observation;
sequential multi-block output is not relabeled as independent block decode.

## Publication boundary

This result is ready for the guarded internal database write only after the
API migration and writer are at the exact source head. The writer must retain
the raw streaming rows, attach numeric derived evidence to the two numeric
criteria, attach `codec_capability=false` to the boolean criterion, re-read the
resolved incremental-decoder dependency inside its serializable transaction,
and prove the protected world/publication fingerprints are unchanged.
No public/upstream publication is authorized by this result.
