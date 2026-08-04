# CUBR-GATEDISARM: profile-independent BWT primary-index gate

Date: 2026-08-04
Base: `611bad41fa0ab4a3fd34f71ed2e830ba351b1af1`
Branch: `codex/cubr-gatedisarm`

## Finding

The v1 BWT wrapper at `code/cubrim-rs/src/codec.rs:7026-7033` narrowed the
wide primary index to the two-byte wire field under `debug_assert!`. On the
web corpus, the disabled-limit path produced `primary_index 134980`, more than
twice the representable maximum `u16::MAX = 65535`. In a release build the
assertion disappeared and `primary as u16` would silently become `3908`.

`EncodeConfig::v1_default()` keeps `use_square_limit: true`, so
`cube_size_limit()` is `65536` on the shipping default. Setting
`use_square_limit: false` changes that limit to `usize::MAX` and permits the
wide single-block path that violates the u16 BWT field. This is an unsafe
non-default configuration; the evidence below does not establish corruption
on the production default.

## Four-cell matrix

| Configuration | Profile | Harness | Result |
| --- | --- | --- | --- |
| `use_square_limit=true` | debug | temporary default BWT corpus harness | 2 passed, 0 failed, 522.70s |
| `use_square_limit=true` | release | temporary default BWT corpus harness | 2 passed, 0 failed, 68.39s |
| `use_square_limit=false` | debug, before guard change | `scheme_roundtrip` | 5 passed, 2 failed, 395.67s; both BWT tests panicked at the debug assertion |
| `use_square_limit=false` | release, before guard change | `scheme_roundtrip` | 7 passed, 0 failed, 62.23s; the gate was disarmed |
| `use_square_limit=false` | debug, after guard change | `scheme_roundtrip` | 5 passed, 2 failed, 396.34s; both BWT tests failed at the real assertion |
| `use_square_limit=false` | release, after guard change | `scheme_roundtrip` | 5 passed, 2 failed, 47.41s; both BWT tests failed at the same real assertion |

The default cells pass in both profiles. The disabled cells now fail in both
profiles, so release no longer turns this invariant violation into a green
round-trip gate.

## Change made

Only `debug_assert!` was changed to `assert!` at the existing u16 narrowing
boundary. The condition, message, cast, wide BWT implementation, decoder,
encoder default, `cube_size_limit`, and `cm_should_try` are unchanged.

The boundary is shared by the six direct BWT value encoders: `BwtEntropy`,
`BwtRans`, `Order2Rans`, `BwtAdaptive`, `BwtContextMix`, and `BwtGeoMix`.
`LzRans` remains the non-BWT member of the competitive family and does not
use this wrapper. The precomputed value-stream competition therefore retains
its existing family-level behavior; no individual scheme was removed from
the disabled-limit test.

## Wire-format conclusion

The current v1 layouts document `primary_index` as `u16 BE`. Supporting a
single block whose BWT primary index exceeds `65535` requires a wider field
and a separate format/version decision. This slice does not widen the field,
change `decode()`, or attempt to make `use_square_limit=false` safe. It makes
the existing gate honest in every profile and leaves the wider-field question
as a separate finding.

## Scope and safety

- No database writes were made.
- The pinned campaign on `162.55.81.5` was not touched.
- PR #28 / `codex/cubr-fuzz-gap` was not touched.
- No wire-format, default-config, decoder, cube-limit, or unrelated source
  behavior was changed.
