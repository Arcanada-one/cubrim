# CUBR-0075 Bounded-State / Allocation Telemetry — Design

Status: design approved by the standing autonomous internal-delivery instruction
Date: 2026-08-14 UTC
Scope: bounded-state hypothesis (`bounded-state`, CUBR-0075) only

This design defines a measurement slice. It makes no measured claim, does not
advance a database row, and does not authorize public or upstream work.

## Context and success criteria

The bounded-state hypothesis is currently pending the `allocator-telemetry`
dependency. Its frozen criteria are:

- WIN: `largest_single_allocation_bytes <= 65,536`;
- GO: `largest_single_allocation_bytes <= 4,194,304`; and
- GO: `auxiliary_memory_bound_ratio <= 1`.

The existing profile-tradeoff run records process-level peak RSS and exact
round trips, but RSS includes process setup and the caller's buffers. Earlier
cycle attribution records allocation-stage calls and retained-state deltas,
but it is throughput attribution rather than an allocator-state measurement.
Neither artifact can answer the registered bounded-state criteria.

The slice succeeds only when it produces content-addressed, per-trial
allocator observations for both static and dynamic Web Profile frames over all
13 canonical `manifest.v3` samples, with three warmups and 30 measured trials
per sample/profile, exact decoded SHA-256 and byte equality on every trial,
complete source/binary/manifest provenance, and an explicit `GO`, `NO_GO`, or
protocol `VOID` result. A threshold failure is a valid negative result; a
provenance, admission, instrumentation, or integrity failure is not a GO or
NO-GO measurement.

## Approaches considered

1. **Instrument the production decoder with a permanent allocator API.** This
   would expose allocation counters from the public/native decoder and could
   be reused by consumers. It also expands the shipped ABI, risks coupling
   allocator semantics to a browser-facing contract, and makes measurement
   code harder to keep out of default builds.

2. **Wrap the existing native decoder library from an external process.** A
   preload or platform allocator tool would avoid source changes, but it cannot
   reliably separate caller, decoder, and output allocations across platforms,
   and the result would depend on host allocator interposition details.

3. **Use a feature-gated standalone Rust probe with a counting global
   allocator.** The probe links the existing `cubrim-web-decoder` crate,
   constructs the same deterministic static/dynamic frames used by the
   canonical corpus, resets counters immediately before each decode, and
   reports allocator scope explicitly. The feature and example are opt-in;
   the normal decoder and shipped ABI remain unchanged.

Approach 3 is the recommendation. It is the smallest falsifiable slice,
keeps the measurement seam separate from the public contract, and can still
report the difference between decoder-owned capacity and caller/output
buffers. Its limitation is explicit: a Rust global allocator measures the
probe's allocation events, not kernel RSS or every allocator-internal arena
page. Those are separate metrics and must not be conflated.

## Architecture and data flow

Add an internal benchmark-only example under `code/cubrim-web-decoder` (or a
feature-gated sibling target if the crate's example dependency rules require
it). It will construct deterministic static and dynamic frames with the
existing `cubrim` dev dependency, then drive the existing native C ABI
(`cbm_stream_new_with_limits`, `cbm_stream_push`, `cbm_stream_finish`, and
`cbm_stream_memory_usage`) so the measured path is the same handle-based seam
used by native consumers. The example will not reach the decoder's private
Rust capacity method directly. Frame construction, manifest validation, and
all JSON serialization happen before each measurement window.

The measurement window is:

1. Validate manifest schema, sample byte count, sample SHA-256, frame mode,
   frame SHA-256, and exact preflight decode.
2. Complete three warmups per sample/profile.
3. Before each measured trial, reset the counting allocator and decoder
   telemetry state. Decode the immutable frame through the native
   `StreamDecoder` path, collect its `memory_usage()`/capacity view, finish the
   stream, and verify exact output SHA-256 and bytes.
4. Drop the returned output and take the post-drop live snapshot. Record
   allocation count, allocated bytes, deallocated bytes, peak live bytes,
   largest single allocation, decoder-retained capacity, caller-owned frame
   bytes, output capacity, and the post-drop retained delta.
5. Derive `auxiliary_memory_bound_ratio` from decoder-owned peak auxiliary
   capacity divided by the measured frame input bytes, with the numerator and
   denominator persisted so the ratio is auditable. Caller input and returned
   output are not silently counted as auxiliary memory.
6. Emit one JSON bundle only after every required cell is valid. A failed cell
   is recorded in the journal and makes the bundle a protocol void rather than
   silently shrinking the sample set.

The probe must not use instrumentation for timing claims. Counting allocation
changes execution cost, so this slice reports allocation/state metrics only and
does not overwrite or reinterpret the profile-tradeoff timing bundle.

## Telemetry contract

Every result records:

- task and phase identifiers;
- Cubrim source SHA, probe source SHA, probe binary SHA, and manifest SHA;
- sample ID, input byte count/SHA, profile, frame mode, frame byte count/SHA;
- warmup/trial counts, seed, CPU affinity, host admission, and disclosure;
- `roundtrip_exact`, decoded SHA, and finish/checksum status;
- `allocation_count`, `allocated_bytes`, `deallocated_bytes`,
  `peak_live_bytes`, `largest_single_allocation_bytes`;
- `caller_input_bytes`, `decoder_retained_peak_bytes`,
  `decoder_retained_after_drop_bytes`, `output_capacity_bytes`,
  `auxiliary_peak_bytes`, and the ratio numerator/denominator; and
- a protocol status and error/void reason, when applicable.

The bundle schema requires exactly 13 samples, two profiles, and 30 valid
trials per sample/profile after three warmups. Aggregates must derive from the
valid rows and must preserve the maximum single allocation and maximum
auxiliary ratio; they must not substitute RSS. A report may state the frozen
criterion result only when the full bundle and all provenance checks pass.

## Safety and failure handling

- The counting allocator must use checked/saturating arithmetic and never
  panic from an allocation hook. Counter overflow, recursive hook entry, or
  inconsistent live-byte accounting invalidates the trial.
- A decoder error, checksum failure, decoded SHA mismatch, frame drift,
  unexpected mode, missing sensor/admission proof, source mismatch, or missing
  trial is a journal-only void. It cannot be converted into a negative result.
- The probe must apply the decoder's existing resource limits and a hard
  process timeout. It must never weaken hostile-input limits to make a trial
  complete.
- The default crate build, default decoder behavior, wire format, native ABI,
  database, API, site, and public/upstream surfaces remain unchanged.
- The first implementation stops at a local evidence report. API/DB
  publication is a separate guarded slice after the bundle schema has been
  reviewed against the existing writer contract; no pending hypothesis is
  advanced by this measurement-only design.

## Tests and verification

Add focused tests for allocator counter reset/overflow/deallocation accounting,
scope separation, schema validation, exact trial cardinality, deterministic
frame provenance, and fail-closed void handling. Add an integration test that
decodes a small static and dynamic frame and asserts exact output plus
non-empty telemetry. Run the existing decoder test suite with the feature off,
then the focused probe tests and feature-enabled build.

Before any result is accepted, verify clean-tree/source hashes, the canonical
manifest hash, singleton affinity, host admission, 3/30 cardinality,
`13 x 2 x 30 = 780` valid cells, zero round-trip mismatches, and the report's
maximums against the raw rows. Preserve the journal and any voided attempts;
never claim a blocker without a current exact-main/provenance check.

## Explicit non-goals

This slice does not add independent-block decoding, change decoder limits,
optimize a hot path, measure ARM silicon, establish streaming first-output
performance, run density optimization, alter the profile-tradeoff result, or
perform a DB/API/site/public/upstream write. Those are separate lanes with
their own contracts.
