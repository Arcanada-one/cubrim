# CUBR-DECODESPREAD — GeoCM follow-up

**Measured:** 2026-08-04 UTC
**Task:** CUBR-0087
**Status:** PASS within the declared two-file diagnostic scope

The initial [`CUBR-DECODESPREAD-20260804.md`](CUBR-DECODESPREAD-20260804.md)
was partial because its first-slice profiler rejected `mr`'s outer mode byte
17 before decoding. This follow-up uses a temporary, feature-gated
measurement extension for GeoCM. Both the GeoCM `mr` archive and the CM2
`nci` archive now produce valid profile JSON and byte-exact round trips under
the same pinned protocol.

## Question and boundary

Run the decode profiler on the same 2 MiB `mr` and `nci` prefix slices used by
STICKY12, then compare stage and function attribution in cycles per compressed
byte. This remains a two-file diagnostic only. It does not generalize to the
Silesia corpus, compare total decode speed, implement an optimization, or
reopen NEW-29.

The GeoCM hooks are a temporary measurement instrument in a detached worktree.
They do not change production source, encoder defaults, decoder behavior,
wire format, or configuration. The only measured GeoCM path here is the
archive's existing MIX inner mode; no claim is made for other GeoCM modes.

## Method and identity

- Inputs are the first 2,097,152 bytes of
  `/home/dev/cubr-cubecore-research/corpus-silesia/mr` and `nci`.
- The source-slice SHA-256 values are `1e254e8d58a0aecd86ce44f29cf00d5531c8b29c1b24efc049371e0f11f59a64`
  (`mr`) and `6788fcc1527c0f62709103e68ac9ab9416461ab00ed1f529b3cf2ae4ab06221e`
  (`nci`). The corpus manifest SHA-256 is
  `d9203058b86b39f94f20b29603a89af5229619b06c78741c64d7098730c39647`.
- The paired archives are the existing STICKY12 inputs: `mr` is 404,341
  bytes, outer mode 17 GeoCM, archive SHA-256
  `6493607227016fc420d17f04778365f4386781dc97c2c0365e1c761a5fc9ff7b`;
  `nci` is 104,139 bytes, outer mode 16 CM2, archive SHA-256
  `1dcc11fa179e3aa0a0b745fba85b5c2187aa382b4b3022ec8ecd8839962b925b`.
- The temporary instrument is based on
  `codex/cubr-0075-profile` at
  `cbdae7d42d4c7374ebee45761d8cb70c738bb7de`. Its uncommitted diff SHA-256
  is `673a0b8b0026dc6b0d8debd0e5163780a0cb1927b28885f36dff12bf784a036f`;
  the patched `geocm.rs` and profiler source hashes, and the profiler binary
  hash, are recorded in [`provenance.txt`](CUBR-DECODESPREAD-GEO-20260804/provenance.txt).
- `CUBRIM_PROFILE=1` and `/usr/bin/time -v` were used. Each profiler process
  was actually pinned with `taskset --cpu-list 0`; the profiler metadata also
  records `--affinity fixed-core`. All outputs were outside the corpus.
- Canonical `origin/main` was refreshed and verified before this follow-up:
  `d5c9ea45e0799464373213500423e7212900d875` by both `git ls-remote` and
  the local remote-tracking ref.

The exact command, source identity, environment, and raw-artifact hashes are
in [`provenance.txt`](CUBR-DECODESPREAD-GEO-20260804/provenance.txt) and
[`SHA256SUMS.txt`](CUBR-DECODESPREAD-GEO-20260804/SHA256SUMS.txt). The full
machine-readable rows are in
[`summary.tsv`](CUBR-DECODESPREAD-GEO-20260804/summary.tsv) and
[`stage-attribution.tsv`](CUBR-DECODESPREAD-GEO-20260804/stage-attribution.tsv).

## Round trip and profile gate

| sample | outer mode | compressed bytes | profile JSON | exact round trip | measured profile |
|---|---|---:|---|---|---|
| `mr` | 17 / GeoCM (inner MIX) | 404,341 | valid | PASS; decoded SHA matches source | PASS |
| `nci` | 16 / CM2 | 104,139 | valid | PASS; decoded SHA matches source | PASS |

The raw JSON records `exact_roundtrip: true` for both files. The temporary
instrument validation also passed the focused GeoCM round-trip test and the
two profile integration tests; the complete output is
[`raw/validation.log`](CUBR-DECODESPREAD-GEO-20260804/raw/validation.log).

## Stage attribution

Values below are cycles per compressed byte, derived from each raw profile's
cycle counter and compressed-input byte count. `N/A` means the profiler marked
the row non-applicable; it is not a measured zero.

| stage | `mr` GeoCM | `nci` CM2 |
|---|---:|---:|
| framing | 0.000331 | 0.005973 |
| entropy | 48,041.209909 | 648,565.372877 |
| transforms | 30,320.211569 | 582,847.978567 |
| allocation | 64.206702 | 4,785.495194 |
| output materialization | 478.899469 | 1,579.129874 |
| match copy | N/A | N/A |

The corresponding total-counter denominators are 105,262.410277 cycles per
compressed byte for `mr` and 1,333,861.181171 for `nci`. They are included for
denominator audit only, not as a total decode-speed verdict.

## Function and model attribution

| function/substage | `mr` GeoCM | `nci` CM2 |
|---|---:|---:|
| `entropy.predict_bit` | 21,425.420677 | 513,804.652589 |
| `transforms.update_bit` | 10,956.075906 | 503,787.548738 |
| `entropy.range_decode` | 2,740.225992 | 9,471.210651 |
| `entropy.range_get_freq` | N/A | 8,346.206935 |
| `transforms.end_byte` | 1,352.541395 | 17,314.871700 |
| `transforms.start_byte` | 926.454324 | 6,678.268775 |

CM2-only model splits are also applicable for `nci`; GeoCM's corresponding
rows are explicitly non-applicable:

| model split | `mr` GeoCM | `nci` CM2 |
|---|---:|---:|
| `model.adaptation` | N/A | 453,819.010265 |
| `model.counter_state_lookup` | N/A | 219,047.946879 |
| `model.dot_products` | N/A | 187,092.612873 |

Stage, substage, and model rows are nested attribution measurements, not a
partition. They must not be summed into a separate speed claim.

## Finding and next hypothesis

The initial GeoCM coverage gap is closed for the stated two-file experiment:
both winning archive modes now have exact profile evidence. Both paths are
dominated by entropy and transform work, but their named breakdown differs:
GeoCM `mr` measures entropy above transforms, while CM2 `nci` has nearly equal
entropy and transform stage attribution plus applicable model-adaptation,
state-lookup, and dot-product rows. The largest named CM2 function rows are
per-bit prediction and update; the largest applicable model split is
adaptation.

The narrow follow-up hypothesis is therefore mode-specific: a later CM2
optimization probe should first target the per-bit prediction/update and model
adaptation path, while a GeoCM probe needs a model-specific breakdown before
assuming the same lever applies. This result does not establish that either
candidate is worth implementing or that the observation generalizes beyond
these two slices.

No production source, encoder, decoder, wire format, configuration, DB,
pinned host, shared backlog, or #28/#29 artifact was changed.

## Raw evidence

- [`raw/mr.decode-profile.fixedcore.json`](CUBR-DECODESPREAD-GEO-20260804/raw/mr.decode-profile.fixedcore.json)
  — exact GeoCM profile.
- [`raw/nci.decode-profile.fixedcore.json`](CUBR-DECODESPREAD-GEO-20260804/raw/nci.decode-profile.fixedcore.json)
  — exact CM2 profile under the same instrument.
- [`raw/mr.decode-profile.fixedcore.stderr`](CUBR-DECODESPREAD-GEO-20260804/raw/mr.decode-profile.fixedcore.stderr)
  and [`raw/nci.decode-profile.fixedcore.stderr`](CUBR-DECODESPREAD-GEO-20260804/raw/nci.decode-profile.fixedcore.stderr)
  — pinned-process timing and exit evidence.
- [`raw/mr.cbr`](CUBR-DECODESPREAD-GEO-20260804/raw/mr.cbr) and
  [`raw/nci.cbr`](CUBR-DECODESPREAD-GEO-20260804/raw/nci.cbr) — exact archive
  inputs.
