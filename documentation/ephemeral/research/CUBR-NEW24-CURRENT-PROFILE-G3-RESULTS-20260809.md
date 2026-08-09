# NEW-24 current-main CM2 attribution G3 result

**Verdict:** `VOID / NO-SELECT`

The one-shot current-main campaign completed its execution and correctness
checks, but the frozen attribution reducer violated its own symbol-identity
contract. The instruction map was keyed by raw Rust-v0 mangled symbols while
`perf script` emitted demangled symbols. Reviewed CM2 samples therefore missed
the map and were silently labelled `other_user` instead of causing a closed
failure.

The prospective protocol classifies any tool/parsing failure as `VOID`.
Accordingly, none of P1–P5 is evaluated, no bucket share or Amdahl ceiling is
admissible, and no candidate is selected. The frozen sample is preserved as
negative evidence and will not be repaired, re-reduced into a candidate, or
entered into the database.

This report applies the decision boundary in
[`CUBR-NEW24-CURRENT-PROFILE-G3-20260809.md`](CUBR-NEW24-CURRENT-PROFILE-G3-20260809.md).
The byte-exact raw tree is
[`CUBR-NEW24-CURRENT-PROFILE-G3-RESULTS-20260809/`](CUBR-NEW24-CURRENT-PROFILE-G3-RESULTS-20260809/),
and the deterministic failure audit is in
[`CUBR-NEW24-CURRENT-PROFILE-G3-ANALYSIS-20260809/`](CUBR-NEW24-CURRENT-PROFILE-G3-ANALYSIS-20260809/).

## Identity and terminal proof

- Source: detached, clean `e0e8bdb2c2df924877d9dcf8a1897810683a147a`.
- Binary SHA-256: `1a49684c5cbbe9106b0b69855b75177e67ffa0c4128bf382921baf9a528b01da`;
  ELF build ID: `649a0cd9dab6d31cf3bbf45aab1f4aa3b890fadf`.
- Runner SHA-256: `12ecee1447f58eb9d3287c73c5ae009975dafad2403db47975b6da37f02e4753`;
  mapper SHA-256: `123f741c5014c4bc329b63c717b673f6b8d1b63f6ee68f01d3cb3d040eae47c4`.
- Systemd unit: `Type=exec`, `Restart=no`, `RuntimeMaxSec=4h5m`, invocation
  `049ef5caefa44ee19dad8b6da03f6a19`; started
  `2026-08-09T19:58:29Z`, exited successfully at
  `2026-08-09T20:39:15Z`, and was observed with `NRestarts=0` from launch
  through terminal state.
- The final output existed, the `.partial` path was absent, and no campaign
  process survived. The later systemd readback was inactive/dead after the
  transient unit had been garbage-collected.
- At capture time the raw tree had 208 files, four directories, no symlinks,
  and no writable entries. All 206 paths in `SHA256SUMS` verify; its only
  exclusions are the manifest itself and the last-written
  `TIMING-DONE.STAMP`.
- The independently recomputed raw identity is content digest
  `9ef754e2efd69b7196240ad664b437f63fe3be0b598c959f6542a16568213154`
  and path digest
  `3ed2d7a908202dc6b2faad7a8bc2710440b7ca134b43b3846d164a09cd0b0d8c`,
  equal at source and destination.

The raw file modes are terminal-capture evidence, not a portable Git checkout
property. Git preserves executable intent but not arbitrary read-only bits.
Reproduction therefore checks committed bytes, path identity, symlink safety,
and the hash-bound terminal observation rather than requiring a checkout to
retain mode `0444`.

## What completed before the void

Admission passed on the required `0-15` affinity with four worker-related
environment variables pinned to 4. The release suite, scheme-roundtrip suite,
fixed-fixture codec identity, archive replays, and all fifteen required decode
round trips completed. Each output matched its registered source by `cmp` and
SHA-256. The service did not retry or substitute a sample.

Those facts establish that the campaign executed once and retained its raw
evidence. They do not rescue the attribution result: the frozen tool parsed
the exact-binary symbol namespace incorrectly.

## Reproduced failure

The frozen map contains keys such as:

```text
_ZN6cubrim3cm23Ctr3upd17hf9318f6ab6a15042E+0x0
```

The corresponding exact-binary samples instead use labels such as:

```text
cubrim::cm2::CmModel::predict_bit+0x57b
```

The reducer's lookup key was `(DSO, symbol+offset)`. Its fallback checked
whether the sample's base symbol appeared in the mapped raw-symbol set. With
one namespace mangled and the other demangled, that check never recognized a
reviewed CM2 symbol. It then assigned the sample to `other_user`.

Across the six fixed records, the independent audit finds exact-binary CM2
sample labels but no exact symbol-key intersection with the frozen map. This
contradicts the preregistered premise that the host `perf script` preserves
Rust-v0 mangled labels, and it violates the rule that an unknown offset inside
the reviewed CM2 set must fail closed. The previously generated zero-target
diagnostics are therefore symptoms of a namespace mismatch, not statistical
evidence.

## Prediction and decision record

| prediction | status | reason |
|---|---|---|
| P1 — current-path change | `NOT-EVALUATED` | The current target shares were not validly joined. |
| P2 — sample-visible mapping coverage | `NOT-EVALUATED` | The producer silently misclassified reviewed exact-binary samples. |
| P3 — StateMap materiality | `NOT-EVALUATED` | The recorded zero target share is inadmissible. |
| P4 — same-byte preset control | `NOT-EVALUATED` | Neither preset has admissible target shares. |
| P5 — repeatability | `NOT-EVALUATED` | Stable zeros from the same invalid join do not prove attribution repeatability. |

This is a tool/parsing failure, so the only valid route is
`VOID / NO-SELECT`. There is no SM32 eligibility, residual-family ranking,
candidate ceiling, measurement row, evaluation, or database pointer.

## Next admissible step

A replacement attribution protocol must land on `main` before a fresh sample
is collected. It must join through normalized object addresses and the exact
binary build ID, with PIE relocation explicitly verified, rather than trusting
presentation symbol spelling. It must map every executable instruction
mechanically, preserve unresolved and ambiguous inline ownership, require
exact period conservation, and make namespace/offset mismatch a pre-sample or
immediate fail-closed condition. The replacement run is a new campaign; this
sample is not retried.

Even a valid replacement attribution result may only name a component family.
A source candidate still requires its own later prospective ceiling,
predictions, acceptance thresholds, and preregistration.

## Reproduction

From the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 python3 documentation/ephemeral/research/test_current_profile_g3_results.py

PYTHONDONTWRITEBYTECODE=1 python3 documentation/ephemeral/research/current_profile_g3_results.py \
  --raw documentation/ephemeral/research/CUBR-NEW24-CURRENT-PROFILE-G3-RESULTS-20260809 \
  --g2-result documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/analysis/result.json \
  --terminal-evidence documentation/ephemeral/research/CUBR-NEW24-CURRENT-PROFILE-G3-ANALYSIS-20260809/terminal-observation.txt \
  --output-dir documentation/ephemeral/research/CUBR-NEW24-CURRENT-PROFILE-G3-ANALYSIS-20260809 \
  --check
```

The reducer checks the raw manifest and exact path set, terminal invocation and
tree identity, admission and terminal journal shape, archive and round-trip
identity, instruction-map ownership and coverage, and the producer's symbol
namespace against every fixed record. Its tests include the exact
mangled-map/demangled-sample failure and reject any attempt to treat it as a
descriptive attribution result.
