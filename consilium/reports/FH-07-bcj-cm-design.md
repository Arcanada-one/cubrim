# FH-07 – BCJ→CM forced executable backend probe design

**Status:** design specification for a private, non‑default experiment

## Context

Prior commit `930758e` wired a call to `encode_cm` after the architectural BCJ
transform in the executable codepath, but the call was structurally inert
because `cm_should_try` requires ≥80% text‑like bytes. ELF/PE files carry
almost no such bytes, so the CM selection gate never opens and the encoder
falls back to the standard competitive backend. The net effect is byte‑identical
output for every executable – the CM candidate is never exercised.

This document specifies a **forced‑only probe** that bypasses the text detection
heuristic for executables and measures whether a CM backend *can* improve upon
the existing BCJ‑wrapped competitive backend after the filter has normalised
control‑flow addresses.

## Design goals

1. Leave the production `encode_bcj` code path entirely untouched (byte‑identical
   output on every existing test).
2. Introduce a **private, ignored benchmark helper** that applies an
   architecture‑matched BCJ filter (x86, ARM64, SPARC) and then compares two
   compressed representations of the filtered byte‑stream:
   - **Baseline:** the unchanged current top-level competitive rail via
     `encode_with_config`.
   - **Candidate:** direct `build_cm_blob` – the CM backend forced without the
     text‑likeness gate.
3. Wrap the smaller representation in the existing `MODE_BCJ` frame. The decoder
   remains unchanged because the mode byte and filter metadata are identical; it
   transparently decompresses whichever backend produced the stream.
4. Run on `mozilla`, `ooffice`, and the SPARC ELF file `sum` from the release
   corpus, sequentially, with `CUBR_THREADS=4`, on dev-ai. The official `exe`
   aggregate contains only `mozilla` and `ooffice`; report `sum` separately as
   a benchmark file whose declared type is `binary`.
5. **Falsify** the probe if:
   - CM never produces a smaller result than the baseline on any file, *or*
   - the original-byte-weighted `mozilla` + `ooffice` exe aggregate does not
     improve.
   In either case the probe is abandoned and no artefacts enter the database or
   the default rail.
6. No claims are made about final ranking; the result is a **go/no‑go signal**
   for a later, broader full‑24 experiment.

## Mechanism

The benchmark helper operates as follows for a single file:

```text
let raw = read_file(path)
let arch = detect_arch(raw)          // ELF e_machine or PE Machine
let bcj_out = apply_bcj(arch, raw)   // reversible filter (size == raw.len())

let baseline = encode_with_config(raw)
let cm_nested = build_cm_blob(bcj_out)
let candidate = wrap_mode_bcj(arch, cm_nested)

record(baseline.len(), candidate.len(), arch, candidate_mode = BCJ)
```

- The baseline is the exact current production rail, including all existing
  top-level candidates.
- The candidate calls the CM encoder directly on the filtered bytes, bypassing
  `cm_should_try`, and wraps that nested blob in a complete `MODE_BCJ` archive.
- Exact complete-archive sizes are recorded. No payload-only estimate is used.
- The helper does not write archive files; it computes sizes in memory and logs
  the exact ratios.

## Test plan

1. Checkout the probe branch, verify that `cargo test` passes and that default
   `encode_bcj` output is byte‑identical to `main` for all executables.
2. Build the existing crate test target. The forced helper remains private and
   is reachable only from an ignored Rust test, not from the CLI or public API.
3. Run on dev‑ai:
   ```bash
   CUBR_THREADS=4 \
   CUBR_FH07_FILES=/root/corpus-full/silesia/mozilla:/root/corpus-full/silesia/ooffice:/root/corpus-full/canterbury/sum \
     cargo test --release test_fh07_actual_files_spike -- --ignored --nocapture
   ```
4. Collect:
   - Exact baseline‑compressed size and CM‑compressed size (in bytes).
   - Ratio relative to uncompressed file size.
   - Which backend won per file.
   - Full RT/cmp correctness: produce a round‑trip archive for each file with
     the winner and verify `cmp` returns 0.
5. Compute the original-byte-weighted ratio over `{mozilla, ooffice}` and
   compare with an exact current-rail remeasurement. Record `sum` separately.
   Historical live metadata provides orientation only and is not substituted
   for the new baseline measurement:
   - Exe aggregate baseline: `0.29355779350869265` (Cubrim current rail).
   - Leader: `0.2748738268008853` (7z). The probe should move the triple closer
     to that target.

### GO gate (proceed to full‑24 experiment)

- CM is selected for **at least one** of the three files **with a measurable
  size reduction** (≥1 byte), AND
- The original-byte-weighted exe aggregate over `mozilla` and `ooffice`
  improves (decreases) compared to the exact current-rail measurement.

### NO‑GO gate (falsified)

- CM never beats the baseline, OR
- The exe aggregate does not improve, OR
- A round‑trip check fails.

If falsified, the probe branch is merged with the negative result documented
and no further action is taken.

## Safety constraints

- The benchmark helper is **never called from any production encode path**.
  The `encode_bcj` function and its callers are unchanged.
- No database records are written, no evolution‑log entries appended, and the
  default rail is not altered.
- The probe does *not* claim that the CM backend is the best choice for all
  executables – it only answers whether BCJ‑filtered executable data can benefit
  from a context‑mixing model that was previously excluded by the text‑only
  heuristic.
- Logs, exact input hashes, commit and bundle hashes, tool versions, and result
  JSON are preserved as provenance. Temporary archive payloads may be removed
  after `cmp=0` is recorded.

## References

- Commit `930758e` – initial wiring of CM after BCJ (inert).
- `cm_should_try` gate in the codebase (requires ≥80% text‑like bytes).
- Existing `MODE_BCJ` encode/decode framework (see architecture‑specific BCJ
  filters: x86, ARM64, SPARC).
- Cubrim leader‑gap report for exe aggregate numbers (`consilium/reports/
  CUBR-leader-gap-literature-resolution.md`).
