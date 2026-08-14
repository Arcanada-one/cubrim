# CUBR-0075 Allocator Telemetry — Hardening Amendment

Status: implementation amendment; no new measured claim
Date: 2026-08-14 UTC
Scope: CUBR-0075 `bounded-state` / `allocator-telemetry`

This amendment records the follow-up hardening applied after an isolated review
of the first telemetry implementation. The original schema-1 result remains a
historical internal record; a new measurement is required under this schema-2
contract before the result is used as current evidence.

## Corrections

- The runner accepts only the repository's canonical
  `bench/web-corpus/manifest.v3.json` path and independently validates the
  ordered sample IDs, paths, byte counts, and input SHA-256 values.
- Every trial's decoded SHA-256, declared output size, caller input size, and
  frame size are checked against the bundle's sample/profile identity. A
  duplicate, reordered, or substituted sample is a journal-only `VOID`.
- Provenance now carries a separate Git source-commit ID plus SHA-256 values
  for the runner source, probe source, probe binary, manifest, and
  preregistration.
- Counting-allocator overflow, underflow, and recursive hook entry set an
  invalid flag and void the trial instead of saturating into a score.
- Successful native `push` and `finish` calls assert that the ABI error state
  is empty. A retained error is a void, even when the return code is otherwise
  successful.
- The duplicate/misleading `decoder_retained_after_drop_bytes` field is
  replaced by `allocator_live_bytes_after`, which names the measured scope.

The default decoder build, native ABI, database, API, site, and public/upstream
surfaces remain unchanged. This amendment changes only the opt-in measurement
probe, its fail-closed runner, tests, and internal research documentation.

## Verification contract

The follow-up must pass the full default decoder suite, the allocator-feature
suite, the runner's end-to-end subprocess test, and the feature probe's unit
tests before a fresh 13-sample × 2-profile × 30-trial Aether run is admitted.
The schema-2 bundle must be read back and independently validated before the
new result report supersedes the historical schema-1 report.
