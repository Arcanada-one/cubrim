# Where a competitor speed comparison may be read from, and where it may not

The epic mandate asks for a decision: should `world_benchmark_operating_point`
carry cross-meta competitor speed, labelled as cross-meta, or must comparisons
always be drawn from the timing aggregate — and then, make reading the wrong one
structurally impossible.

**Decision: comparisons come from `world_benchmark_timing_aggregate`, and only
within a single `meta_id`. `world_benchmark_operating_point` must stay
cubrim-only and must never gain a competitor speed column.**

Measured read-only against `arcanada_cubrim` on 2026-08-11.

## The measurement that decides it

`world_benchmark_timing_aggregate` — 420 rows:

| meta_id | distinct archivers | rows |
|---:|---:|---:|
| 7 | 10 | 100 |
| 24 | 10 | 100 |
| 35 | 10 | 100 |
| 36 | 10 | 100 |
| **37** | **1** | 10 |
| **38** | **1** | 10 |

`world_benchmark_operating_point` — 30 rows, `archiver` = `cubrim` on all 30,
`compress_mib_s`/`decompress_mib_s` populated on all 30, spanning
`meta_id` ∈ {36, 37, 38}.

So competitors were measured at meta 36 and never at 37 or 38. The operating
points span all three.

## Why the view must not carry competitor speed

A competitor column on the operating-point view would be **legitimate for meta
36 and fabricated for metas 37 and 38** — two thirds of its rows. The only way
to populate those two is to import meta-36 competitor numbers under a
meta-37/38 row, which states that a competitor was measured at an operating
point where it was not.

The view's own `competitor_note` already says so:

> Competitors were measured once under meta 36 and are NOT re-run per preset.
> Any comparison against them must be labelled as cross-meta, or left empty.

"Labelled as cross-meta" is the weaker of the two options that note allows, and
it is the wrong one here. A label is a property of a *presentation*; the hazard
is a property of the *row*. Once a competitor figure sits on a meta-38 row, every
future reader — a query, a chart, an API serialiser, a session in a hurry — has
to remember to carry the label with it. The project has already established that
empty is safer than annotated: *a measurement void goes to the journal, never
the DB; unmeasured stays empty, never estimated.* A cross-meta import is an
estimate wearing a citation.

Choosing "always draw from the timing aggregate" costs nothing, because the
comparison that is legitimate — meta 36, ten archivers, same meta — is already
available there in full.

## The invariants, stated as queries

These are the checks; a reader or a reviewer can run them directly.

**I1 — the operating-point view is single-archiver.**

```sql
SELECT count(DISTINCT archiver) FROM world_benchmark_operating_point;
-- must be exactly 1, and that archiver must be 'cubrim'
```

**I2 — no competitor speed leaks into it.** The view must expose speed columns
for cubrim only; a non-cubrim row with a non-null `compress_mib_s` or
`decompress_mib_s` is a violation.

```sql
SELECT count(*) FROM world_benchmark_operating_point
WHERE archiver <> 'cubrim';
-- must be 0
```

**I3 — a cross-archiver comparison never spans metas.** Any query comparing
archivers must group or join on an equal `meta_id`; a comparison that mixes
`meta_id` values is cross-meta and must be labelled or refused.

```sql
SELECT meta_id, count(DISTINCT archiver) AS archivers
FROM world_benchmark_timing_aggregate GROUP BY meta_id;
-- only metas reporting >1 archiver support a comparison at all
```

I3 is the one that matters most and the one a reader is most likely to skip:
metas 37 and 38 report a single archiver, so **no competitor comparison exists
at those operating points in any table**. The correct output there is empty, not
borrowed.

## On "structurally impossible"

Fully closing this needs a database-side constraint — a `CHECK` or trigger
asserting I1/I2 on the table that backs the view, so a violating row cannot be
written rather than merely being noticed afterwards. That is the right
enforcement and it is deliberately **not applied here**.

`arcanada_cubrim` is the live source of truth and is under continuous concurrent
write by parallel sessions working the benchmark track. Adding a constraint to a
shared production table mid-flight can fail an unrelated in-flight write, and the
failure would surface in someone else's lane as an unexplained error. A schema
change there wants the benchmark track's own change window, not a drive-by from
an adjacent lane.

What this note does instead: fixes the decision so the question is not reopened
per-reader, and states the invariants as runnable queries so the constraint, when
it is written, has an agreed specification rather than a fresh argument. The
enforcement is owed; the decision is not.

## Boundary

Read-only throughout. No row, column, constraint, view, or grant was created,
altered, or dropped; `evaluation` remains 0 and no measurement field was
written. This note issues no benchmark result and changes no published figure.
