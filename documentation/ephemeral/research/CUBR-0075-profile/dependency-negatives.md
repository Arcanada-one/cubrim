# CUBR-0075 — Measured Negative Dependencies

This is cumulative evidence from the first and deep attribution slices, not an
optimization, evaluation, or release verdict. The raw sources are
[`attribution.json`](attribution.json) and [`deep-attribution.json`](deep-attribution.json).
The original record was authorized by `/home/dev/LUNA-0075VERDICT.md`; the deep
hotspot and roadmap update is authorized by `/home/dev/LUNA-0075HOTSPOT.md`.

## Dependency 14 — `independent-block-container`

Across 720 non-warmup observations, framing accounted for exactly **196,008 cycles**
out of **2,259,933,725,206 named-stage cycles**. It is displayed as 0.00% in the
aggregate table and cannot explain the measured throughput gap. A block/container
design may still be relevant to streaming or first-output latency; those are separate
pending goals and are not cleared by this negative.

## Dependency 8 — `allocator-telemetry`

Across the same 720 measured observations, allocation accounted for exactly
**8,942,160,152 cycles** across **90,480 calls** (0.40% of named-stage cycles). The
retained-state delta after output drop was **0 bytes in all 792 observations**. This
is a measured negative for throughput leverage, not a bounded-memory proof. The
allocator counters remain useful as attribution instrumentation.

## Dependency 13 — `table-driven-entropy-build`

The deep per-operation run measured the actual range-coder calls, rather than treating
the whole `entropy` stage as one undifferentiated target:

| operation | cycles | calls | cycles/call |
|---|---:|---:|---:|
| `entropy.range_get_freq` | 23,209,864,070 | 452,038,080 | 51.3 |
| `entropy.range_decode` | 26,382,709,116 | 452,038,080 | 58.4 |
| **combined** | **49,592,573,186** | **904,076,160** | **54.9 average** |

Together these calls are **2.0185%** of the 2,456,882,895,434 detailed substage
cycles (displayed as about **2.01%**). If both operations were free, Amdahl permits
only **1.0206×** maximum speedup. This is a measured negative for the web-throughput
route; it does not rule out a coder improvement for a different non-CM path or for
archival engineering.

## Roadmap status

Dependency 12, `web-profile-prototype`, is now the mandatory next route because the
current decoder's full-model ceiling is only 22.5× against a 227× gate. Dependency 15,
`simd-decode-build`, is insufficient alone against that arithmetic, although it may
still be useful for the archival product. Dependencies 14, 8, and 13 are the three of
eleven registered directions now resolved negatively by measurement.

## Instrument sanity

`woff2-medium-inter-latin-v20` used the raw-store mode and measured about **0.6
cycles/output byte**, with 0.0% in both CM2 stages. It is a sanity check that the
instrument does not invent transform or entropy work for an already-compressed input.

All three dependencies are recorded as measured negatives; no database evaluation rows
or pending-hypothesis advances were made.
