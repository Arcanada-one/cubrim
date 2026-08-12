# The operating-point speed contract was merged but never applied

Date: 2026-08-12. Task: CUBR-0087 (Phase C). Scope: one production DDL apply, no
measurement, no DB row written.

## The gap

`https://api.cubrim.com/api/operating-points` reported, for all three published
operating points:

```json
"speed_contract_status": "migration_pending"
{"preset":"max","meta_id":36,"timing_status":"not_measured","encode_mib_s":null,"decode_mib_s":null}
{"preset":"balanced","meta_id":37,"timing_status":"not_measured","encode_mib_s":null,"decode_mib_s":null}
{"preset":"web","meta_id":38,"timing_status":"not_measured","encode_mib_s":null,"decode_mib_s":null}
```

The campaign `method` prose on the same endpoint still read *"NO timings were
taken, because a sibling session shared the host"*.

That prose was accurate **when written**. The Phase C size campaign published at
2026-07-31 11:03 UTC took no timings. The timing campaign started later the same
day — `run_id` `meta36-preset-max-timing-20260731T153924Z`, i.e. 15:39:24 UTC —
and its rows were imported into `world_benchmark_timing_file` on **2026-08-04**.
So the measurement existed for eight days while the public surface said it did
not.

This is the failure mode the programme has flagged repeatedly: a route sweep
returns 200 on every URL and cannot see that the content is stale.

## Root cause: a merged migration that was never applied

`cubrim-api` carries `migrations/20260809_operating_point_speed_contract.sql`,
merged with its own test suite (`test/operatingPointSpeedMigration.test.ts`). The
API reads three views through `Promise.allSettled` and, on an undefined-relation
error, fail-opens to `speed_contract_status: 'migration_pending'` rather than
erroring. So the API was **honest, not broken** — it was reporting that the views
did not exist.

Confirmed: of the three views the contract requires
(`..._cubrim_speed_measurement`, `..._same_meta_speed_comparison`,
`..._speed_reference`), **none** existed in `arcanada_cubrim`.

## Checks made before touching production

1. **Preconditions** — the migration's own guards raise on unexpected state.
   Verified read-only first: `world_benchmark_timing_run` exists, 0 run/meta
   mismatches in `_timing_file` and `_timing_aggregate`, 0 duplicate
   `(run_id, meta_id)` pairs. So its `UNIQUE` and `NOT VALID` FK additions could
   not fail on data.
2. **Dry run of the view logic** — the base view's body was extracted and run as
   a plain read-only `SELECT`, before any DDL, to confirm the strict filters
   (`runner_sha256` regex, exact `file_count`, `sum(orig) = orig_bytes`, uniform
   sample and warmup counts) actually admit our rows rather than yielding an
   empty view:

   | meta | preset | files | orig bytes | samples | warmup | encode MiB/s | decode MiB/s |
   |---|---|---|---|---|---|---|---|
   | 36 | max | 24 | 314,749,364 | 3 | 1 | 0.0230 | 0.0866 |
   | 37 | balanced | 24 | 314,749,364 | 3 | 1 | 0.0378 | 0.0876 |
   | 38 | lowmem-decode | 24 | 314,749,364 | 3 | 1 | 0.0401 | 0.1179 |

   These reproduce the aggregate figures reached independently by summing
   per-file wall clock in FINDINGS **F22** — `0.0230 -> 0.0378 MiB/s` encode for
   `max -> balanced`, and `0.1179 / 0.0866 = 1.36x` decode for `lowmem-decode`.
   Two different paths through the same campaign agree.

## Applied

The migration ran under `ON_ERROR_STOP=1` inside its own `BEGIN … COMMIT`:
4 views created, 3 `GRANT SELECT` to `cubrim_api_ro`, 4 comments. It is
idempotent and additive; views are droppable.

Result on the live endpoint:

```json
"speed_contract_status": "available"
{"preset":"max","meta_id":36,"timing_status":"measured","encode_mib_s":0.0230,"decode_mib_s":0.0866}
{"preset":"balanced","meta_id":37,"timing_status":"measured","encode_mib_s":0.0378,"decode_mib_s":0.0876}
{"preset":"web","meta_id":38,"timing_status":"measured","encode_mib_s":0.0401,"decode_mib_s":0.1179}
```

## Two consequences worth recording

**`world_benchmark_operating_point_vs_competitors` is gone, by design.** Line 136
of the migration drops it, and the new pair supersedes it with a stricter split:
`..._same_meta_speed_comparison` carries outcome-bearing comparisons *only* when
meta, scope, protocol, host, manifests, runner and file population all match
exactly; `..._speed_reference` carries incompatible same-meta and cross-meta
measurements with their mismatch reasons and **no comparative outcome fields**.
Nothing consumed the dropped view — the only repository references are the
migration's own `DROP` and the test asserting it. The site reads the API, not the
database.

**The contract publishes zero like-for-like competitor comparisons.**
`same_meta_speed_comparisons` is **0**; `non_like_for_like_speed_references` is
**27**. No competitor timing at these metas clears the exact-match bar, so the
API now says so explicitly instead of implying comparability. That is the
intended behaviour, and it is the honest one: the earlier `vs_competitors` view
labelled two thirds of its rows `cross-meta-36`, which a consumer could drop.
Under the new split a consumer cannot silently promote a reference into a
comparison, because the reference view has no outcome field to read.

## Verification after

- `/api/operating-points` 200, `/api/evolution` 200.
- `cubrim.com/en/evolution/benchmark` 200, `/en/download` 200, `/` 302 (language
  redirect, expected).

No DB row was written, no measurement was created, and no prose verdict was
edited. The only change is that measurements taken on 2026-07-31 and imported on
2026-08-04 are now visible where they were already supposed to be.
