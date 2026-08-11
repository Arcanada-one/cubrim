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

## On "structurally impossible" — already true, and this corrects an earlier claim

An earlier revision of this note said a `CHECK` or trigger was owed, and deferred
it because the database was assumed to be under continuous concurrent write.
Both halves were wrong, and probing settled it.

**`world_benchmark_operating_point` is a VIEW, not a base table**, and its
definition ends:

```sql
  FROM world_benchmark_meta m
    JOIN world_benchmark_aggregate a ON a.meta_id = m.id
    LEFT JOIN world_benchmark_timing_aggregate t
      ON t.meta_id = a.meta_id AND t.scope = a.scope AND t.archiver = a.archiver
 WHERE m.task = 'CUBR-0087-phaseC' AND a.archiver = 'cubrim';
```

`a.archiver = 'cubrim'` is hardcoded in the view body. **I1 and I2 are therefore
already structurally impossible to violate** — the view cannot emit a
non-cubrim row, and no constraint could be attached to it anyway, because a view
has no rows of its own to constrain. The `competitor_note` documents a property
the SQL already guarantees rather than a convention a reader must uphold.

The timing join is equally tight: it matches on `meta_id`, `scope` **and**
`archiver`, so the speed columns on any row come from that row's own meta. No
cross-meta value can enter the view through the join.

The deferral reason was also overstated. Probed directly: one active backend
(this session's own query) and **zero locks** on the target relation. The
database was quiet, not busy.

**What remains genuinely unenforced is I3, and no constraint can fix it.** I3 is
a property of how a *reader* queries `world_benchmark_timing_aggregate` — a
comparison that groups across `meta_id` values is cross-meta, and that mistake
happens in the query, not in stored data. The defence there is the measurement
in this note: metas 37 and 38 carry a single archiver, so a competitor
comparison at those operating points does not exist to be read. Nothing is owed
against this view.

## Boundary

Read-only throughout. No row, column, constraint, view, or grant was created,
altered, or dropped; `evaluation` remains 0 and no measurement field was
written. This note issues no benchmark result and changes no published figure.
