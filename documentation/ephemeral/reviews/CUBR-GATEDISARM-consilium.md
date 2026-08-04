# CUBR-GATEDISARM — BWT Ceiling Consilium

**Date:** 2026-08-04
**Branch:** `codex/cubr-gatedisarm`
**PR:** [#29](https://github.com/Arcanada-one/cubrim/pull/29)
**Reviewed head:** `bd2e9fc95dff978faab3985a818669eaef0504a7`
**Base:** `611bad41fa0ab4a3fd34f71ed2e830ba351b1af1`

## Consilium recommendation

**Question:** What is the correct resolution of the v1 `u16` `primary_index`
ceiling when `use_square_limit=false` permits a BWT block larger than 65536,
given that the default path is clean, the wire format is public under ADR-0003,
and the gate must remain red when the invariant is violated?

**Panel:**

- Parfit — architecture/protocol lens
- Huygens — QA and security lens
- Dalton — implementation and performance lens

**Verdict:** **Choose option 2: reject unsafe BWT/configuration use in v1.**

The v1 format must retain `primary_index: u16` big-endian. A BWT path that
would produce an index above `u16::MAX` must fail deterministically before
narrowing or emitting v1 bytes. The eventual implementation should use a
stable encoding/configuration error with identical debug and release behavior;
the current assertion is evidence that the invariant is real and that the
gate is correctly disarmed, not the implementation of this follow-up.

This preserves the public v1 wire contract and is the smallest reversible
resolution. The cost is explicit: `use_square_limit=false` cannot provide the
six affected BWT schemes when their input exceeds the representable range.
Non-BWT schemes and bounded BWT inputs remain available. A wider field belongs
to a separately specified format version with an explicit discriminator and
compatibility tests; it must not reinterpret the v1 two-byte slot.

## Evidence baseline

- `use_square_limit=true` passed the temporary BWT web-corpus round-trip tests
  in both debug and release profiles.
- With `use_square_limit=false`, the existing wide-path test had 5 passed and
  2 failed in debug. After the profile-independent guard, release also has 5
  passed and 2 failed.
- The two failures are `bwt_geo_mix_roundtrips_the_web_corpus` and
  `bwt_entropy_roundtrips_the_web_corpus`; both expose
  `primary_index 134980 exceeds u16::MAX`.
- `EncodeConfig::v1_default()` retains `use_square_limit=true`, while false
  returns `usize::MAX` from `cube_size_limit()`.
- The six affected wrappers are BWT entropy, rANS, order-2 rANS, adaptive,
  context-mix, and geometric-mix encoders. Their v1 layouts document a two-byte
  primary index.
- PR #29's lossless-round-trip check is intentionally red; reproducibility,
  formatting, and lineage checks are green. No merge is authorized.

## Panel positions

### Parfit — Architecture/protocol

**Position:** Conditional support for option 2.

The u16 field is a v1 wire invariant, not an incidental implementation limit.
Rejecting the unsafe BWT/configuration preserves existing readers and makes a
future version migration explicit. The accepted cost is loss of wide BWT
coverage in v1 and a separately scoped protocol upgrade later.

The first red proof must be a deterministic release-mode fixture at
`primary_index = 65536` with `use_square_limit=false`: it must return the
defined rejection, emit no v1 bytes, and never reach the narrowing operation.
The challenge to option 1 is that widening without an end-to-end discriminator
and reader negotiation creates framing ambiguity for existing v1 readers.

### Huygens — QA and security

**Position:** Support option 2.

The rejection must be stable and fail closed in both profiles. The existing
v1 u16-BE range remains unchanged; a future v2 may widen the field only behind
explicit version/capability negotiation. Wide-path tests should remain as
negative cases that assert the error and the absence of partial output. The
first red proof is the 134980-index corpus case succeeding, truncating, or
behaving differently between debug and release. The challenge to option 1 is
that a version story not yet proven end to end cannot be allowed to change v1
decoding semantics.

### Dalton — Implementation/performance

**Position:** Support option 2.

Use a typed range/configuration error before serialization. Preserve coverage at
the boundaries: 65535 passes, while 65536 and 134980 reject with no partial
frame. This avoids silently corrupting the primary index and leaves chunking as
a deliberate future codec design rather than an emergency wire workaround. The
challenge to option 3 is that the primary index is block-global; chunking
changes BWT semantics and requires new framing and per-chunk indexes, making it
effectively a more complex new format.

## Debate and convergence

The three completed positions were unanimous after analysis, so no second
debate round was needed. Their shared priority ordering was correctness and
wire compatibility first, then reversibility and implementation simplicity.
No completed panelist dissented from option 2. The challenges to options 1 and
3 are retained above as the relevant dissent signals for the later design
slice, rather than being treated as proof that those options are impossible.

An initial broader four-role dispatch did not return within two bounded wait
windows and was closed. The final record therefore claims a three-position
completed panel, not a seven-agent consensus.

## Failure-mode table

| What can fail | Probability | Impact | Detection | Mitigation |
|---|---:|---:|---|---|
| Unsafe BWT reaches the v1 u16 cast | Medium | High | 65536/134980 negative fixtures succeed or emit bytes | Return a typed error before narrowing and keep the release gate red |
| Debug and release disagree | Medium | High | Same wide fixture has different result by profile | Run both profiles and assert the same error classification |
| Rejection emits a partial frame | Low | High | Output buffer is non-empty after rejected encode | Build/commit no v1 frame until validation succeeds; test empty output |
| Future widening is mistaken for v1 compatibility | Medium | High | Old decoder misreads a new stream or framing offset | Add an explicit format version/discriminator and cross-version fixtures |
| Chunking changes compression semantics without proof | Medium | Medium | Density/regression benchmark diverges from baseline | Treat option 3 as a separate codec design with its own wire and density review |

## Conditions and assumptions

1. ADR-0003 remains authoritative for deployed v1 readers and its two-byte
   primary-index field is not silently redefined.
2. The later implementation returns a stable, inspectable error before any
   v1 serialization and does not silently substitute a different scheme unless
   that fallback is separately specified and tested.
3. `use_square_limit=true` remains the v1 default and its existing clean
   round-trip coverage is preserved.
4. A future wider-index format is a separate design/implementation task with
   version negotiation, backward compatibility, and release-profile coverage.

## Scope boundary

This consilium records the decision only. It does **not** implement option 2,
widen the wire field, alter `decode()`, change encoder defaults, change
`cube_size_limit()` or `cm_should_try()`, make PR #29 green, merge either open
PR, touch the database, or run the campaign host. The red lossless check is the
authoritative evidence that the invariant violation remains visible.
