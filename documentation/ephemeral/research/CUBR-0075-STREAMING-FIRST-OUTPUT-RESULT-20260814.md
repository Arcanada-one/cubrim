# CUBR-0075 Streaming / First-Output Result — 2026-08-14

Status: **valid measurement — NO_GO**
Scope: Cubrim-only API-to-sink streaming evidence

## Decision

The existing `StreamDecoder` is a real incremental API, but the frozen
first-output predicate is not universal across the canonical corpus. Only
`120/390` measured streaming trials (`30.7692%`) handed any output to the
independent sink before the encoded frame ended. The median streaming
first-output input fraction was `1.0`; the maximum was `1.0`. Under the frozen
rule, the valid result is **NO_GO**.

This is a capability/latency result, not a decoder-correctness failure. All
`390/390` streaming and `390/390` whole-buffer control trials finished with
exact byte-for-byte output and matching SHA-256 digests. The whole-buffer
control had `0/390` pre-EOF output events, as expected.

## Frozen protocol and evidence

- Preregistration: `CUBR-0075-STREAMING-FIRST-OUTPUT-PREREG-20260814.md`;
  SHA-256 `934bf279500d71851e28d7588822a06fa3fd5646775345fa53e9e9c502998908`.
- Corpus: `cubr0074-web-real-v3`, 13 samples, `manifest.v3.json` SHA-256
  `43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5`.
- Matrix: 13 samples × (`streaming`, `whole_buffer`) × 3 warmups × 30
  measured trials; schedule seed `75075`.
- Web Profile block size: `65,536` bytes; streaming input pieces: `4,096`
  bytes.
- Raw bundle: `/home/dev/evidence/CUBR-0075-STREAMING-FIRST-OUTPUT-20260814/streaming-first-output.json`;
  SHA-256 `d5016998eb8ca8cfb5d8cea5741e1841979e340608e42ea4e49bc46a41250604`.
- Bundle status: `COMPLETE`; 858/858 records valid; round-trip failures `0`.

The first output event is measured at the handoff from `StreamDecoder::push`
to an independent digest sink. It is not a browser paint, a network socket
timestamp, or a subprocess stdout timestamp. A sequential multi-block stream
is not treated as an independent-block container.

## Provenance and admission

The accepted run used source commit
`ae8737f6a0e69563fb2c6828d468779fc951d3c2` on `arcana-devs`, `x86_64`,
`rustc 1.97.1 (8bab26f4f 2026-07-14)`, with CPU affinity `0` and 16 logical
CPUs. The admission load was `4.16357421875 / 16 = 0.260223388671875` before
and after the run. Available temperatures ranged up to `87.0 C`, below the
strict `90 C` ceiling.

Content hashes:

| Artifact | SHA-256 |
|---|---|
| Probe source | `398ef87ec18090edc4191b6a7b230a9359c6b62fd0d1a0b224a9441b6b8bd53a` |
| Probe binary | `7980c55c02e54e30338af536323896d03d62d7e2abce72638c5a004bb0f5fdef` |
| Runner | `c2b276a935ee0c32eb2236be5fd92af9e208b5145210418062ee76847edfca5c` |
| Preregistration | `934bf279500d71851e28d7588822a06fa3fd5646775345fa53e9e9c502998908` |
| Corpus manifest | `43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5` |

## Per-sample result

Each row below contains 30 measured streaming trials. `before/30` counts
strictly pre-EOF first-output events; the fraction is the median first-output
input bytes divided by encoded frame bytes.

| Sample | Pre-EOF | Median input fraction | Frame bytes |
|---|---:|---:|---:|
| `css-medium-tailwind-v2` | `0/30` | `1.000000` | 10,361 |
| `html-large-web-codec-v2` | `30/30` | `0.566842` | 14,452 |
| `html-medium-home-v2` | `0/30` | `1.000000` | 5,563 |
| `javascript-medium-magic-string-v2` | `0/30` | `1.000000` | 9,375 |
| `javascript-medium-sourcemap-codec-v2` | `0/30` | `1.000000` | 3,522 |
| `javascript-small-resolve-uri-v2` | `0/30` | `1.000000` | 2,797 |
| `json-api-large-world-benchmark-v2` | `30/30` | `0.222066` | 18,445 |
| `json-api-medium-web-benchmark-v2` | `30/30` | `0.862134` | 9,502 |
| `json-api-small-hypotheses-v2` | `0/30` | `1.000000` | 1,558 |
| `source-map-large-magic-string-v2` | `30/30` | `0.865002` | 18,941 |
| `source-map-small-sourcemap-codec-v2` | `0/30` | `1.000000` | 2,407 |
| `wasm-medium-cubrim-decoder-v3` | `0/30` | `1.000000` | 20,551 |
| `woff2-medium-inter-latin-v20` | `0/30` | `1.000000` | 23,650 |

The four early-producing samples are the larger inputs that cross the
multi-block boundary. The nine `0/30` rows are valid observations of the
current sequential frame behavior, not omitted or failed trials.

## Boundaries and next route

This result closes the measurement slice only. It does not authorize a
database/API/site write, independent-block redesign, ARM claim, throughput
claim, bounded-state claim, or public/upstream release. The existing streaming
API remains useful for multi-block progressive delivery, but a universal
first-output guarantee would require a separate design decision and a new
preregistration; this result provides no authorization to invent that change.
