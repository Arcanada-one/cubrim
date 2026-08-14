# CUBR-0075 Bounded-State / Allocation Telemetry — Preregistration

Status: frozen preregistration
Scope: CUBR-0075 `bounded-state` hypothesis and its `allocator-telemetry` dependency
Date: 2026-08-14 UTC

This note freezes the measurement protocol. It reports no measured values and
makes no evaluation or production claim.

## Corpus and execution protocol

- Corpus: canonical `bench/web-corpus/manifest.v3.json`, schema version `2`,
  exactly 13 samples with manifest byte counts and SHA-256 values.
- Profiles: deterministic `cubrim-static` (`EncodeConfig::web_profile`) and
  `cubrim-dynamic` (`cubrim::encode_web_dynamic`), both with a 65,536-byte
  Web Profile block size.
- Decoder seam: existing native `cubrim-web-decoder` handle ABI and
  `StreamDecoder` implementation, driven in chunks no larger than 65,536 bytes.
- Per sample/profile: exactly 3 warmups followed by exactly 30 measured trials.
- Trial order: deterministic randomized schedule with seed `75075`.
- Admission: one effective CPU, singleton `taskset` verification when needed,
  load-per-CPU at most `1.0`, and every available temperature strictly below
  `90 C`; admission is checked before and after the probe.
- Integrity: every measured frame and decoded output is SHA-256 checked;
  decoded bytes must equal the original bytes exactly; checksum/finish must
  succeed.
- The probe has no database side effects. Failed protocol cells are retained
  in a journal-only void record and do not become partial aggregates.

## Allocator observations

The counting allocator is installed only in the feature-enabled benchmark
probe. It records successful allocation/reallocation/deallocation events and
uses a recursion guard, saturating arithmetic, and a baseline live-byte
snapshot. Each valid row records:

- allocation count, allocated/deallocated bytes, peak live bytes, and largest
  requested allocation;
- known caller-owned input frame bytes and declared output bytes;
- peak decoder-owned capacity from `cbm_stream_memory_usage`;
- decoder-owned post-drop capacity and the post-drop live delta; and
- `auxiliary_peak_bytes` plus its explicit denominator and ratio.

`auxiliary_peak_bytes` is the conservative decoder-owned peak capacity minus
the known input frame bytes and declared output bytes, saturating at zero.
`auxiliary_memory_bound_ratio` is that numerator divided by the input frame
byte count. This is allocator/capacity evidence, not kernel RSS, allocator
arena-page accounting, or a timing measurement.

## Frozen criteria

The result is derived only after all `13 x 2 x 30 = 780` valid cells pass:

- `WIN` if maximum `largest_single_allocation_bytes <= 65,536`;
- otherwise `GO` on that criterion if the maximum is `<= 4,194,304`;
- `GO` on the auxiliary criterion if maximum
  `auxiliary_memory_bound_ratio <= 1`.

If any required cell, provenance field, admission proof, mode, round trip,
counter invariant, or schema cardinality is invalid, the run is `VOID` and no
threshold result is asserted. A valid threshold failure is recorded as
`NO_GO`, never silently omitted or relabeled as a void.

## Provenance and non-claims

The bundle must bind the exact source SHA, probe source SHA, feature-enabled
probe binary SHA, canonical manifest SHA, host/CPU/affinity, seed, trial
counts, and this preregistration reference. The measurement does not change
the default decoder, wire format, native ABI, database, API, site, or public
and upstream surfaces. It does not measure timing, ARM silicon, independent
block behavior, streaming first-output performance, density, or the separate
profile-tradeoff result.
