# CUBR-0075 Streaming / Early-Output Performance — Publication Augmentation Result

Status: **valid measurement — NO_GO**  
Scope: Cubrim native ABI-to-sink evidence for `streaming-early-output-performance`  
Date: 2026-08-15 UTC

## Decision

The publication augmentation preserves the original complete 13-sample ×
2-mode decoder matrix byte-for-byte and adds one fresh, frame-verified encode
timing per corpus sample. The original numeric and capability observations are
unchanged: first output passes at `23,650` bytes, the auxiliary-capacity bound
fails at `681.9358151476251`, and independent-block decode is explicitly false.
The valid result remains **NO_GO**.

This is native decoder-capacity and source-derived encoder-resource evidence.
It is not browser paint, HTTP transport, total-process RSS, ARM, production, or
public/upstream readiness evidence.

## Evidence and provenance

- Frozen augmentation preregistration:
  `documentation/ephemeral/research/CUBR-0075-STREAMING-PERFORMANCE-PREREG-R2-20260815.md`;
  SHA-256 `b01beaa89fc40f7f5aff3aee23cb67bcd6dc42486316e5320f5bf5e03dc8ef64`.
- Base decoder bundle:
  `/home/dev/evidence/CUBR-0075-STREAMING-PERFORMANCE-20260815/streaming-performance.json`;
  SHA-256 `b8493a33a3ee603cfce89799c99849abb7203e7c86d8b6953b1bdfb76ec9f4c2`.
- Publication bundle:
  `/home/dev/evidence/CUBR-0075-STREAMING-PERFORMANCE-R2-20260815/streaming-performance.json`;
  SHA-256 `540f42d31e6cc746fcd873807fcb24b7a3b858c6cccc626306efd8b5ee3f5dba`.
- Base-bundle SHA recorded in the publication bundle:
  `b8493a33a3ee603cfce89799c99849abb7203e7c86d8b6953b1bdfb76ec9f4c2`.
- Cubrim source commit: `4e847baaf0c17c0561677669ffd0932a4c4a447e`.
- Probe source SHA-256:
  `490f9ac041f99ba3a54e6880f6a621172ce74add093f5256328d778658cf1456`.
- Probe binary SHA-256:
  `bf97c9b3d456dcfececf0306495ff8a16cbf2fc6fb91e17bb44a29501890fc8a`.
- Runner SHA-256:
  `2997d64a6aff4c6fdab9fdff988aa7f9da0ab9fe2585d7ed8bbc05967a6e6d52`.
- Corpus manifest SHA-256:
  `43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5`.
- Host: `arcana-devs`, `x86_64`, CPU affinity `0`.

## Matrix preservation and encode timing

The publication bundle contains `858` trial rows: `390` measured streaming
trials and `390` measured whole-buffer controls, plus the frozen warmups. All
raw decoder fields, mode assignments, output hashes, latency values, and
memory observations compare equal to the base bundle after removing only the
new `compression_duration_ns` field. Exact round-trip and sink failures remain
zero.

For each of the 13 canonical samples, the probe performed one fresh
`cubrim::encode_with_config` call with Web Profile enabled and a `65,536`-byte
block size. It verified frame length and SHA-256 against the preloaded frame,
then recorded a positive monotonic duration. That real source-derived value is
attached to every row for the sample; repeated rows are decoder observations,
not independent encode-timing replicates. The observed range was
`8,940,708` ns to `1,408,246,702` ns. No zero, sentinel, inferred, or
non-finite compression value was used.

## Threshold observations

| Criterion | Observed | Preregistered bar | Result |
|---|---:|---:|---|
| Maximum first output after input | 23,650 bytes | ≤ 65,536 bytes | GO |
| Maximum auxiliary capacity ratio | 681.9358151476251 | ≤ 1.0 | NO_GO |
| Independent block decode | false | exact boolean true | NO_GO |

The auxiliary ratio is the preregistered ABI-capacity calculation:
`max(cbm_stream_memory_usage) - frame_bytes - declared_output_bytes`, divided
by `frame_bytes`. It is not an RSS measurement.

## Publication boundary

The guarded API writer may publish the eight canonical resource metrics from
this bundle after the API source and live schema are at the exact verified
heads. This result does not authorize public or upstream publication.
