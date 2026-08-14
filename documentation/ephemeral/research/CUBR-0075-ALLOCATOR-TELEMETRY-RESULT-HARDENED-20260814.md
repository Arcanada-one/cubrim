# CUBR-0075 Bounded-State / Allocation Telemetry — Hardened Result

Status: measured, independently validated, not database-published
Scope: CUBR-0075 `bounded-state` / `allocator-telemetry` only
Date: 2026-08-14 UTC

This report supersedes the historical schema-1 measurement recorded before
the telemetry hardening. It does not close CUBR-0075 as a whole, reinterpret
the profile-tradeoff result, or authorize public or upstream action.

## Provenance and host

- Cubrim source commit measured: `fb1edbf87d5f662ebc9f679885d05fc3bf3930f9`
  (corrective provenance PR #232 landed on `main`).
- Probe binary SHA-256:
  `4eb54d1a59eb55ef70d3f9e008d1c6805e758ead8ab8c8d9c182b89cb538eb17`.
- Probe source SHA-256:
  `70c1471b8261c10bbdccf0391b6bece3a27ed690bc0b5541aba780cc4f2326e0`.
- Runner SHA-256:
  `14cfe828fcc0571cb2dc786cb11e3fcd2687b5eab2e8832c8f3a8fff06fa1a67`.
- Canonical manifest SHA-256:
  `43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5`.
- Frozen preregistration SHA-256:
  `efc7a171d2f52296a7b32a677a00e0ee817a18153af0e0b50d0cf85be1873e90`.
- Accepted bundle SHA-256:
  `0d2af1076eb8e1ce3148ba684b07da49108ef35d43fa47be6147d675dbe3d6ab`.
- Accepted journal SHA-256:
  `47f213b733a30687269d3b93ebbf55024c8700069e22e452d9926dfa0dc711d3`.

The accepted run executed on Aether `dev-ai` (`x86_64`, 64 logical CPUs),
singleton-pinned to affinity `[0]`. Admission passed before and after the
probe. The recorded load per CPU was `0.0204238896484375` before and
`0.0200347900390625` after; maximum sampled temperature was `56.85 C`.

## Frozen protocol and integrity

The schema-2 probe ran the canonical 13 samples with static and dynamic Web
Profile frames, three warmups, and 30 measured trials per sample/profile:
780 exact trial cells, seed `75075`, and 65,536-byte chunks and blocks. Every
trial passed native stream finish/checksum validation, byte-exact decoded
output comparison, and SHA-256 verification. Round-trip failures: `0`.

The runner independently checked the canonical manifest path and ordered
sample identity, every input and decoded digest, all counter/ratio invariants,
raw-row summary derivation, separate Git-commit and file-hash provenance, and
the final decision.

## Measurement

| profile | trials | max largest allocation | max decoder-retained peak | max allocator peak-live delta | max auxiliary ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| static | 390 | `320,976 B` | `1,708,973 B` | `661,381 B` | `681.9358151476251` |
| dynamic | 390 | `320,976 B` | `1,713,445 B` | `665,853 B` | `657.460396039604` |

Across both profiles there were `73,200` allocation events. The maximum
allocator baseline live delta after a trial was `64 B`. The auxiliary metric
is the registered conservative decoder-capacity bound after subtracting known
frame-input and declared-output bytes; it is not kernel RSS, allocator arena
usage, or a timing measurement.

## Frozen decision

The bounded-state result is `NO_GO`:

- allocation WIN (`<= 65,536 B`): not satisfied;
- allocation GO (`<= 4,194,304 B`): satisfied;
- auxiliary-memory GO (`<= 1`): not satisfied; overall maximum was
  `681.9358151476251`.

This is a valid negative for the registered conservative capacity metric. It
does not prove a decoder leak, establish a kernel-RSS limit, or identify a
timing regression.

## Preflight void and boundaries

An earlier preflight against exact Cubrim main `42ede7ea982732ad96848b9619c7a81c20354e81`
was voided before scoring because the newly hardened runner incorrectly
classified the 40-hex Git commit ID as a SHA-256 digest. The preserved
preflight void journal SHA-256 is
`bdca268c7203cc08efd53e5899181f4edbbc560a6a6de1519393854c94afbdcb`.
That journal is not part of the accepted bundle or its score. PR #232
corrected the contract and passed the full Cubrim CI suite before this fresh
run.

Local retained evidence is under
`/home/dev/evidence/CUBR-0075-ALLOCATOR-TELEMETRY-HARDENED-20260814/`.
The measurement did not write API or database rows. ARM silicon, streaming
first-output performance, independent-block behavior, density/WIN, and the
remaining CUBR-0075/CUBR-0072 lanes remain separate. No public or upstream
action was taken.
