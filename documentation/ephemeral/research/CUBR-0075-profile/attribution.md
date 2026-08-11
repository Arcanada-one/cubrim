# CUBR-0075 — Decode Attribution, First Slice

Status: `COMPLETE` for the mandated attribution slice. This is an attribution result,
not an optimization or evaluation verdict.

## Result

The measured decode cost is in the CM2 model/coder loop, specifically the model-state
transforms and entropy/range work. On the fixed-core run, weighted medians over all
965,410 decoded bytes were:

| Stage | Time (ns/decoded byte) | Cycles (cycles/decoded byte) | Share of named stage time |
|---|---:|---:|---:|
| transforms | 6,045.184 | 20,532.984 | 51.93% |
| entropy | 5,505.359 | 18,844.328 | 47.29% |
| output materialization | 51.401 | 70.904 | 0.44% |
| allocation | 40.011 | 144.166 | 0.34% |
| framing | 0.001 | 0.002 | 0.00% |
| match/copy | N/A for all v2 samples | N/A | N/A |

The named stages account for 11,641.956 ns/byte versus 12,278.324 ns/byte of total
fixed-core decode time; the remaining 5.18% is deliberately left unattributed to
dispatch, stall accounting, and other code outside this first slice. The result does
not hide that residual inside a named stage. Thus the 227x-scale problem is not header
framing, allocation, or output copying: approximately 99.2% of the named attribution
is the CM2 transform plus entropy loop.

The one-core comparison (one decoder thread without an affinity mask) measured
11,638.995 ns/byte and 41,900.420 cycles/byte. The fixed-core comparison measured
12,278.324 ns/byte and 44,202.006 cycles/byte, 5.49% slower on this host. Pinning did
not improve this run; the comparison is scheduler/affinity context, not a parallelism
claim.

## Size-band comparison

The boundary is binary 64 KiB (`65,536` bytes). The 65,257-byte CSS sample is retained
in the near-boundary lower band.

| Band | Samples | Decoded bytes | One-core ns/B | Fixed-core ns/B | Fixed-core cycles/B |
|---|---:|---:|---:|---:|---:|
| at or below 64 KiB | 8 | 204,924 | 9,987.938 | 11,368.682 | 40,927.290 |
| above 64 KiB | 4 | 760,486 | 12,083.896 | 12,523.440 | 45,084.425 |

The larger band is slower, but this slice does not infer a threshold mechanism from
that observation. The pending window/streaming hypotheses remain pending.

## Per-sample fixed-core attribution

The table gives the median for the 30 measured trials (three warmups are excluded from
the median) and preserves the raw observations in `attribution.json`.

| Sample | Bytes | Band | Mode | Total ns/B | Entropy ns/B | Transforms ns/B |
|---|---:|---|---|---:|---:|---:|
| css-medium-tailwind-v2 | 65,257 | at-or-below | CM2 | 13,210.381 | 5,803.391 | 6,537.474 |
| html-large-web-codec-v2 | 227,968 | above | CM2 | 11,479.063 | 5,094.095 | 5,713.225 |
| html-medium-home-v2 | 25,031 | at-or-below | CM2 | 10,573.790 | 4,695.175 | 5,193.218 |
| javascript-medium-magic-string-v2 | 42,936 | at-or-below | CM2 | 14,750.864 | 6,532.141 | 7,303.905 |
| javascript-medium-sourcemap-codec-v2 | 14,590 | at-or-below | CM2 | 11,159.584 | 4,798.860 | 5,506.926 |
| javascript-small-resolve-uri-v2 | 9,866 | at-or-below | CM2 | 11,261.962 | 4,700.574 | 5,543.954 |
| json-api-large-world-benchmark-v2 | 320,976 | above | CM2 | 12,374.641 | 5,669.145 | 6,042.182 |
| json-api-medium-web-benchmark-v2 | 98,948 | above | CM2 | 14,494.807 | 6,565.843 | 7,074.715 |
| json-api-small-hypotheses-v2 | 13,880 | at-or-below | CM2 | 13,352.652 | 5,842.490 | 6,444.378 |
| source-map-large-magic-string-v2 | 112,594 | above | CM2 | 13,329.725 | 5,897.060 | 6,616.505 |
| source-map-small-sourcemap-codec-v2 | 9,700 | at-or-below | CM2 | 11,377.668 | 4,756.900 | 5,623.383 |
| woff2-medium-inter-latin-v20 | 23,664 | at-or-below | raw | 0.136 | N/A | N/A |

All 11 CM2 archives and the one raw archive are represented. The raw WOFF2 sample has
no entropy or transform loop and is not evidence for the CM2 gap.

## Measurement and provenance

- Programme handoff: CUBR-0074 supplied the Gate2 reference measurement and decode
  consilium; this CUBR-0075 plan is the execution of that consilium's first slice.
- Corpus: `bench/web-corpus/manifest.v2.json`, manifest SHA-256
  `fecc83c1e6559d361d0029024393a3cc98909f0c45dea3a2f0c4f11b75a3a2bf`.
- Protocol: release mode, 3 warmups plus 30 measured trials, 12 samples, two affinity
  modes; 792 observations in total, all 792 exact round trips.
- Host: `arcana-devs`, Linux 6.8.0-124-generic, x86_64, 16 CPUs.
- Source: commit `97c81df4133deacbe4ffe5798d30051b56e9ebe3`.
- Encoder binary SHA-256:
  `6acc41379c2de44bc09ea732b8d7ee8cb25ab22d78f254f4ed243a44f6fe5359`.
- Profile binary SHA-256:
  `4fc0875015b9c74441f1ecfe2eb3939f3da07c96b85ed18ff2d7a5c6bdebc4f9`.
- Cycle source: `rdtsc-x86_64`; cycles are attribution counters, not a portable
  replacement for a privileged hardware performance-counter run.
- Allocator window: counters are sampled around decode and again after the output is
  dropped. Retained-state delta was 0 bytes in all 792 observations, but this is not a
  bounded-memory proof and does not replace RSS or a future bounded-state gate.

The complete raw records and per-affinity medians are in
[`attribution.json`](attribution.json). No database evaluation/evidence rows were
written, and no pending hypothesis was advanced.
