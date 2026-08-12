# CUBR-0074 — the publication path exists, and could not have run

Date: 2026-08-12
Scope: `cubrim-api` write path for `web_benchmark_*`. No production database was
touched; no measured number was published anywhere.

## What the previous record got wrong

`datarim/insights/INSIGHTS-CUBR-0074.md` (2026-08-12) says there is "no
publication path in the repository" and that the guarded writer "is a writer
someone still has to build". That is wrong, and the error is a scope one: it
looked in the Cubrim repository's `bench/`, where nothing writes the database,
and concluded the path did not exist. It lives in the other repository.

On `cubrim-api` `origin/main` the whole path is present and has been for weeks:

- `src/webBenchmarkWriter.ts` — 1658 lines: backup, restore-list verification,
  advisory lock, serializable transaction, staged revalidation, projection
  compare, world-benchmark isolation assertion, publication readback, redacted
  journal. It also carries its own `parseCliArgs` and `main`.
- `scripts/web-benchmark-guarded-write.sh` — the operator entry point, which
  execs `dist/webBenchmarkWriter.js`.
- `test/webBenchmarkWriter.integration.test.ts` — 729 lines, including a live
  arm gated on `pg_isready` with `PGSERVICE=cubrim-test`.

What was true is that it had never run. Three things stopped it, and none of
them is "write the writer".

## 1. The bundle contract was three corpus generations behind

`parseWebBenchmarkBundle` pinned, as literals:

| pin | contract on main | what the harness emits |
|---|---|---|
| `corpus.manifest_name` | `manifest.v1.json` | `manifest.v3.json` |
| `corpus.manifest_sha256` | `9a0fcb56…` | `43474bfc…` |
| `corpus.manifest_schema_version` | `1` | `2` |
| canonical sample list | 8 project-authored fixtures | 13 real-world samples |
| `toolchain` length | `3` | `5` |
| codec keys | `gzip`, `brotli`, `zstd` | `gzip-9`, `brotli-11`, `brotli-5`, `zstd-19`, `zstd-3` |
| `corpus.samples[].attribution` | rejected by `.strict()` | present on all 13 |

Any bundle the current harness produces is rejected by the first pin it meets.
The corpus pin is right in kind — the run is only comparable to the one before
it if both measured the same bytes — so the fix re-pins it to v3 rather than
loosening it: manifest name, digest, schema version and the complete sample list
still have to match exactly, and the sample list was regenerated from
`bench/web-corpus/manifest.v3.json` after re-hashing all 13 payloads against it
(0 mismatches) and confirming that file's own sha256 is `43474bfc…`.

## 2. The writer's own role was never provisioned in the repository

`verifyWriterPrivileges` demands a non-superuser role named
`cubrim_web_benchmark_writer` with SELECT on all web and world benchmark tables,
INSERT on exactly eight, column-scoped UPDATE on two, and no DELETE or TRUNCATE
anywhere. No migration grants any of it. The grants exist on the arcana-devs
gate container because someone typed them there; a database rebuilt from
`migrations/` has the schema and none of the privileges.

## 3. Applying the hypothesis migration disarms the writer

`migrations/20260727_web_benchmark_hypothesis.sql` grants
`cubrim_web_benchmark_writer` SELECT+INSERT on seven
`web_benchmark_hypothesis*` tables. The writer refuses to run when its role can
insert anywhere outside its publication allowlist, and the hypothesis tables are
not on it. So the migration that seeds the hypothesis catalogue is also the one
that stops the benchmark from being published.

Production has that catalogue: `GET /api/web-benchmark/hypotheses` returns 200
with `counts.total = 17`. Production is therefore the arm where the guarded
write fails.

## The A/B that settles it

PostgreSQL 18.4 in the `cubr0074-gate1-pg18` container. Two scratch databases
cloned with `TEMPLATE arcanada_cubrim` (the live `arcanada_cubrim` was not
modified). Same bundle, same compiled writer, same server, same role.

| database | migrations applied | result |
|---|---|---|
| `cubr0074_control` | hypothesis only | exit 1 — `benchmark writer role exceeds its mutation allowlist` |
| `cubr0074_control` | + `20260812_web_benchmark_writer_role.sql` | dry run passes every preflight |
| `cubr0074_publish_probe` | + same role migration | **committed** |

The middle row is the isolation: the same database flips from refusing to
passing on the role migration alone.

The committed run, read back as `postgres`:

```
corpus=1 samples=13 codecs=5 runs=1 trials=1950 metrics=9750 summaries=325 publication=1
corpus     phase-a:manifest.v3.json | 43474bfc… | schema=2 | n=13
run        validated | cubr-web-a-1c09ec21ab527c5ae97d68b80768ec78a582cfa6
publication published | LEGAL-0061:terminal-compliant
world_benchmark_* unchanged
```

**The bundle was the synthetic test fixture** — the real corpus v3 identity with
fabricated timings — because the point was to exercise the write path, not to
publish a measurement. Nothing here is a benchmark result and none of it went
anywhere near production.

## Still open

- **Publishing the real thing still needs a Phase A run on corpus v3 on a quiet
  host.** That was the previously recorded blocker and it remains one; it is now
  the *only* one. arcana-devs sat at 0.75–3.4 load per CPU against a 1.0
  admission ceiling through the night.
- **`pg_dump` version skew is unverified on whatever host would publish.** The
  writer shells out to `pg_dump`/`pg_restore`; arcana-devs carries the 16.14
  client against an 18.4 server, which refuses. This run used the container's
  own 18.4 binaries. Before a production publication, check that the publishing
  host's `pg_dump` is at least the server's major version — a skew here fails
  the run at backup time, which is the safe direction, but it fails it.

## The shape of the mistake, for next time

Three defects in series on a path nobody had executed: a contract pinned to a
retired generation, provisioning that lived only on one host, and two shipped
migrations whose grants contradict a shipped check. Each is invisible to unit
tests, because each is about the seam between an artefact and its environment.
A path that has never been run end to end should be assumed broken in as many
places as it has seams, and the cheapest way to find out is to run it against a
throwaway clone rather than to read it.
