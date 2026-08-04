# CUBR-DECODESPREAD — decode-stage attribution

**Measured:** 2026-08-04 UTC
**Task:** CUBR-0087
**Status:** PARTIAL — `nci` has a valid decode profile; `mr` is byte-exact but the existing profiler rejects its mode before decoding.

## Question and boundary

Run the existing feature-gated decode profiler on the same 2 MiB `mr` and `nci`
prefix slices used by STICKY12, then express stage/function attribution in
cycles per compressed byte. This is a two-file diagnostic only. It does not
generalize to the Silesia corpus, compare total decode speed, implement an
optimization, or reopen NEW-29.

## Method and identity

- Inputs are `head -c 2097152` from
  `/home/dev/cubr-cubecore-research/corpus-silesia/`; both slice hashes match
  STICKY12.
- The paired release encoder and decode profiler are from the clean
  `codex/cubr-0075-profile` worktree at
  `cbdae7d42d4c7374ebee45761d8cb70c738bb7de`.
- `CUBRIM_PROFILE=1` and `/usr/bin/time -v` were used. The final profiler
  process was actually pinned with `taskset`: core 0 for `nci`, core 1 for
  `mr`; `--affinity fixed-core` is retained in the profiler JSON metadata.
- Archives and outputs were created under `/tmp/cubr-decodespread.v7hl1u`,
  outside the corpus. The exact archive inputs, raw JSON/logs, and hashes are
  preserved in
  [`CUBR-DECODESPREAD-20260804/`](CUBR-DECODESPREAD-20260804/).
- `origin/main` was verified before recording the mode-coverage blocker:
  `611bad41fa0ab4a3fd34f71ed2e830ba351b1af1` by both `git ls-remote` and the
  local remote-tracking ref.

The full provenance and binary/source/corpus hashes are in
[`provenance.txt`](CUBR-DECODESPREAD-20260804/provenance.txt). The machine
readout is [`summary.tsv`](CUBR-DECODESPREAD-20260804/summary.tsv), and the
derived per-compressed-byte rows are
[`stage-attribution.tsv`](CUBR-DECODESPREAD-20260804/stage-attribution.tsv).

## Round trip and profile gate

| sample | outer mode byte | outer mode | compressed bytes | archive SHA-256 | ordinary decode / `cmp` | profiler result |
|---|---:|---|---:|---|---|---|
| `mr` | 17 | GeoCM | 404,341 | `6493607227016fc420d17f04778365f4386781dc97c2c0365e1c761a5fc9ff7b` | PASS / PASS | **BLOCKED**: profiler rejects mode 17 before decode |
| `nci` | 16 | CM2 | 104,139 | `1dcc11fa179e3aa0a0b745fba85b5c2187aa382b4b3022ec8ecd8839962b925b` | PASS / PASS | PASS: exact profile JSON |

Both ordinary decodes produced 2,097,152 bytes and matched the source slice
SHA-256 byte-for-byte. The `mr` failure is explicit in
[`raw/mr.decode-profile.stderr`](CUBR-DECODESPREAD-20260804/raw/mr.decode-profile.stderr):
the first-slice profiler supports only cube, raw, and CM2. There is no `mr`
stage attribution to compare; treating its ordinary decode timing as a stage
result would be unsupported.

## Valid attribution: `nci` only

The denominator below is the compressed input size, 104,139 bytes. Values are
from the fixed-core raw profile, independently recomputed from its cycle and
nanosecond totals; the profiler’s raw JSON uses output-byte denominators.

### Stages

| stage | cycles / compressed byte | ns / compressed byte |
|---|---:|---:|
| entropy | 675,775.80 | 193,147.66 |
| transforms | 616,619.23 | 178,085.26 |
| allocation | 3,384.15 | 939.78 |
| output materialization | 1,657.21 | 1,135.89 |
| framing | 0.0062 | 0.0023 |
| match copy | not applicable for this CM2 path | not applicable |

### Substages and model splits

| function/substage | cycles / compressed byte |
|---|---:|
| `transforms.update_bit` | 534,245.73 |
| `entropy.predict_bit` | 537,281.72 |
| `transforms.end_byte` | 18,397.81 |
| `entropy.range_decode` | 9,718.64 |
| `entropy.range_get_freq` | 8,538.77 |
| `transforms.start_byte` | 7,520.14 |
| `model.adaptation` | 482,890.38 |
| `model.counter_state_lookup` | 245,419.19 |
| `model.dot_products` | 178,013.28 |

These rows are nested attribution measurements, not a partition: stage,
substage, and model rows intentionally overlap. They are not used as a total
decode-speed verdict.

## Finding and next hypothesis

For this one supported observation, `nci` decode attribution is concentrated
in CM2 entropy and transform work. The largest model split is adaptation, and
the largest named substages are per-bit prediction and update. The narrow
hypothesis for a later run is that `nci`’s high decode cost is driven chiefly
by per-output CM2 model adaptation/prediction/update, rather than by its
compressed byte count alone.

`mr` cannot test that hypothesis: its winning archive is GeoCM and the current
instrument has neither a supported mode gate nor equivalent GeoCM attribution
hooks. A later measurement should add or use a mode-aware GeoCM profiler, then
repeat both files under the same pinned protocol. Until then, no cross-file
stage comparison and no corpus-wide decoder claim is proven.

No source, encoder, decoder, wire format, or configuration implementation was
changed. No DB write, pinned-host contact, shared backlog edit, or #28/#29
change was made.

## Raw evidence

- [`raw/nci.decode-profile.json`](CUBR-DECODESPREAD-20260804/raw/nci.decode-profile.json)
  — exact-round-trip profile and raw cycle/nanosecond counters.
- [`raw/mr.decode-profile.stderr`](CUBR-DECODESPREAD-20260804/raw/mr.decode-profile.stderr)
  — fail-closed mode-coverage proof.
- [`raw/mr.cbr`](CUBR-DECODESPREAD-20260804/raw/mr.cbr) and
  [`raw/nci.cbr`](CUBR-DECODESPREAD-20260804/raw/nci.cbr) — exact profile
  inputs.
- [`SHA256SUMS.txt`](CUBR-DECODESPREAD-20260804/SHA256SUMS.txt) — hashes for
  every preserved raw artifact.
