# CUBR-0075 Profile Tradeoff Measurement — Preregistration

Status: frozen preregistration
Scope: internal CUBR-0075 measurement
Date: 2026-08-14

This note freezes the measurement protocol. It reports no measured values and makes no outcome claims.

## Frozen corpus and protocol

- Frozen corpus/probe source: canonical `manifest.v3`.
- Source artifacts and probe hashes are content-addressed and frozen in the run journal.
- Code under test:
  - cubrim static `EncodeConfig::web_profile`
  - `cubrim::encode_web_dynamic`
- Block size: `65,536` bytes.
- Per profile/resource cell: `3` warmup trials, then `30` randomized valid trials.
- Every valid trial must pass exact SHA-256 digest verification and byte-for-byte round-trip verification.
- Execution is pinned to one admitted CPU.
- The measuring process performs no database writes.
- Void handling is journal-only: any trial that fails protocol or integrity checks is recorded as a journal-only void and excluded from primary aggregates.

## Outcome definitions

- `dynamic_compression_throughput` = the lower 95% bootstrap bound over the `30` per-trial values, where each per-trial value is `(aggregate dynamic input-bytes) / (aggregate dynamic encode-seconds)` for that trial.
- `dynamic_ratio_loss_vs_static` = exact corpus-wide value `(sum of dynamic frame bytes / sum of static frame bytes) - 1`.

## Preexisting GO/WIN thresholds

- `dynamic_compression_throughput`: GO threshold = `50,000,000 bytes/s`.
- `dynamic_ratio_loss_vs_static`: GO threshold = `0.05`; WIN threshold = `0.02`.

No additional thresholds are introduced in this note.

## Non-claims

This preregistration does not assert that any threshold is met, does not report measured values, and does not claim static or dynamic superiority, production readiness, or performance regression. It also does not authorize public release or upstream action.
