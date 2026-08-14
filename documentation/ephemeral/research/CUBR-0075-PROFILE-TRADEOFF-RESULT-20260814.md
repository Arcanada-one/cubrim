# CUBR-0075 Profile-Tradeoff Measurement — Result

Status: measured and guarded-published
Scope: the CUBR-0075 static/dynamic profile-tradeoff axis only
Date: 2026-08-14 UTC

This report records the authoritative result of the frozen profile-tradeoff
protocol. It does not close CUBR-0075 as a whole, and it does not authorize
public release or upstream action.

## Provenance

- Cubrim source: `origin/main` `b98fc1e0f320aef0666f5c4bbe594afcb30c008b`.
- API source: `origin/main` `d90be8b9e89232b62be75b39d1ea068e5992ab7f`.
- Frozen preregistration:
  `documentation/ephemeral/research/CUBR-0075-PROFILE-TRADEOFF-PREREG-20260814.md`, SHA-256
  `e7b3d4a8e58e107e12f37d65945a019d9d4e690dfc9bcf6fe0c693fa95b2065b`.
- Profile runner SHA-256:
  `07b2d864a651d52574a3b0bbb7331d3503196bff37258e1b932632e5d2ba321a`.
- Rust probe SHA-256:
  `957d5b5184c4bb49f6b94ad623cf7570ca258aa1262df4be26bd0a0fca8f37df`.
- Canonical corpus manifest SHA-256:
  `43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5`.
- Measured bundle SHA-256:
  `2e8761ebc69b7d4d0ecf924b93818478a2ae5c4959a62e9b8b6f7b510ccda730`.

The measurement ran on Aether (`dev-ai`, `x86_64`, EPYC host, 64 logical
CPUs) with effective affinity `[0]`, three warmups, 30 valid trials per
profile/resource cell, 13 canonical samples, seed `75075`, 5,000 bootstrap
iterations, and a 65,536-byte block size. The host passed admission throughout
the run: load per CPU was approximately `0.0094`, maximum observed temperature
was `52.85 C`, and peak child RSS was `35,127,296` bytes.

The bundle contains `13 x 2 x 30 = 780` valid trial cells. Every cell passed
the exact decoded SHA-256 and byte-for-byte round-trip checks. No trial was
silently discarded; protocol failures are journal-only voids by the frozen
preregistration.

## Measurement

| Profile | Aggregate frame bytes | Lower 95% bootstrap compression throughput |
| --- | ---: | ---: |
| static | `141,124` | not applicable |
| dynamic | `153,049` | `4,640,975.645926329 bytes/s` |

The exact corpus-wide dynamic ratio loss versus static is
`0.08450015589127302` (`8.450015589127302%`). The dynamic throughput point
estimate is `4,654,933.789596479 bytes/s`; its bootstrap interval is
`[4,640,975.645926329, 4,670,271.787464028] bytes/s`.

## Frozen decision

The result is `NO-GO` for this profile-tradeoff axis:

- Throughput GO floor: `50,000,000 bytes/s`; measured lower bound:
  `4,640,975.645926329` — not satisfied.
- Ratio-loss GO ceiling: `0.05`; measured value:
  `0.08450015589127302` — not satisfied.
- Ratio-loss WIN ceiling: `0.02`; measured value:
  `0.08450015589127302` — not satisfied.

This is an honest negative result. It does not imply that every future codec
profile or hardware target is negative, and it does not convert the result
into a production recommendation.

## Guarded database publication

The API writer was delivered on `d90be8b9e89232b62be75b39d1ea068e5992ab7f`.
CI run `31813054382` passed typecheck, tests, build, and security; canonical
deployment run `31813101868` passed cutover and off-host exact-health checks.
The writer was exercised first in dry-run mode and then in commit mode using
the least-privilege writer role. Both runs verified schema, backup, role,
publication, world-data, and terminal-journal invariants. The commit retained
DB and hypothesis backups and recorded the commit intent and terminal result.

Independent DB readback identifies:

- run `30088`, status `validated`, scenario `resource_codec`;
- 780 resource results, 5,460 metrics, and 182 validated summaries;
- two profile codec builds with the same Cubrim source and binary provenance;
- evaluation `15`, dependency `resolved`, lifecycle `published`, decision
  `NO_GO`;
- derived values sourced from 13 and 26 rows respectively;
- all three frozen evidence predicates false.

The live `/api/web-benchmark/hypotheses` response renders the same profile
card and values. Its catalog counts are `total=17`, `evaluated=5`,
`pending_dependency=8`, and `awaiting_measurement=4`. The existing public
`/api/web-benchmark` pointer remained unchanged by the hypothesis publication.
The normalized pre/post world export SHA-256 is identical:
`90e2bfc2a5691d8f66993202ccd21e7c5c9bbd6d32225e25b77e7449a6a8790d`.

## Evidence and remaining boundaries

The retained local evidence directory is
`/home/dev/evidence/CUBR-0075-PROFILE-TRADEOFF-20260814/`. It contains the
measured bundle, Aether and commit journals, DB and hypothesis backups, pre/post
world exports, and the independent DB readback manifest. The measured bundle
SHA-256 is recorded above; the commit journal SHA-256 is
`a041a16b2faee9a002d77dff178277727c5ed1d664abd41f7a30b71c827391ab`.

This report closes the profile-tradeoff measurement/publication slice only.
Remaining CUBR-0075/CUBR-0072 boundaries include ARM-silicon evidence,
additional speed axes, streaming/incremental decoder behavior
(`incremental_decoder_nonempty_output=false` in this build), density/WIN
criteria, and the rest of the parent research sequence. CUBR-0080 public or
upstream work was not touched.
