# CUBR-0075 — Measured Negative Dependencies

This is evidence from the first attribution slice, not an optimization or evaluation
verdict. The raw source is [`attribution.json`](attribution.json); the verdict that
authorizes this record is `/home/dev/LUNA-0075VERDICT.md`.

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

## Instrument sanity

`woff2-medium-inter-latin-v20` used the raw-store mode and measured about **0.6
cycles/output byte**, with 0.0% in both CM2 stages. It is a sanity check that the
instrument does not invent transform or entropy work for an already-compressed input.

Both dependencies are recorded as measured negatives; no database evaluation rows or
pending-hypothesis advances were made.
