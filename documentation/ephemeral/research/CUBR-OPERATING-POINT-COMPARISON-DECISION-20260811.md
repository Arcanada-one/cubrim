# Where a competitor speed comparison may be read from, and where it may not

The epic mandate asks for a decision: should `world_benchmark_operating_point`
carry cross-meta competitor speed, labelled as cross-meta, or must comparisons
always be drawn from the timing aggregate — and then, make reading the wrong one
structurally impossible.

**Finding: the schema already answers this, correctly, and better than the
question's framing suggests. Nothing needs to change.**

Measured read-only against `arcanada_cubrim` on 2026-08-11.

> **Revision history matters here.** Two earlier revisions of this note were
> wrong. The first said a `CHECK` constraint was owed; the second corrected that
> but still argued the "labelled as cross-meta" option should be rejected. Both
> errors came from writing before probing the schema. What follows is the
> measured state.

## What the schema actually does

There are two views, and the split between them is the answer.

**`world_benchmark_operating_point`** — the clean view. Its body ends:

```sql
 WHERE m.task = 'CUBR-0087-phaseC' AND a.archiver = 'cubrim';
```

`archiver = 'cubrim'` is hardcoded, so it **cannot** emit a competitor row: 30
rows, all cubrim, spanning `meta_id` ∈ {36, 37, 38}. Its timing join matches on
`meta_id`, `scope` **and** `archiver`, so no cross-meta value can enter through
the join. No constraint is owed — and none could be attached anyway, because a
view has no rows of its own to constrain.

**`world_benchmark_operating_point_vs_competitors`** — the comparison view,
separate and named for what it is. It pins competitor timing explicitly and
labels every row with its basis:

```sql
CASE WHEN op.meta_id = 36 THEN 'same-meta-36' ELSE 'cross-meta-36' END
  AS competitor_timing_basis
...
JOIN world_benchmark_timing_aggregate t
  ON t.meta_id = 36 AND t.scope = op.scope AND t.archiver <> 'cubrim'
```

Measured contents:

| `competitor_timing_basis` | rows | distinct metas | competitors |
|---|---:|---:|---:|
| `same-meta-36` | 90 | 1 | 9 |
| `cross-meta-36` | 180 | 2 | 9 |
| **unlabelled** | **0** | — | — |

## Why this is the right design

The mandate framed it as a binary — carry labelled competitor speed, or forbid
it and always use the timing aggregate. The schema took a third option that is
stronger than either: **keep the operating-point view free of competitor data,
and put the comparison in a separate view where every row states its own
basis.**

An earlier revision of this note argued against labelling on the grounds that
"a label is a property of a presentation, the hazard is a property of the row."
That objection does not survive contact with the implementation. Here the label
*is* a property of the row — `competitor_timing_basis` is a column, populated on
100% of rows, machine-readable by any consumer. It is not a caption a reader has
to remember to carry.

The join is also pinned rather than incidental: `t.meta_id = 36` is written into
the view, so the comparison cannot silently drift onto some other meta as new
metas land. A row is `cross-meta-36` because the operating point is 37 or 38 —
stated, not inferred.

## The one residual risk, precisely

Neither view can be misread by accident. What remains is a **consumer** that
selects from `world_benchmark_operating_point_vs_competitors` and drops
`competitor_timing_basis` from its projection, then presents the 180 cross-meta
rows as if they were same-meta measurements.

That is not fixable by a database constraint, because the data is correct and
fully labelled at the point it leaves the database; the error would occur
downstream. The defence is the measurement above: **two thirds of that view's
rows are cross-meta**, so any consumer showing competitor speed at an operating
point must carry the basis column or restrict to `meta_id = 36`.

Stated as a check a reviewer can run against any consumer:

```sql
-- A consumer of the comparison view must either carry competitor_timing_basis
-- or filter to same-meta rows. This shows the split it would be hiding:
SELECT competitor_timing_basis, count(*)
FROM world_benchmark_operating_point_vs_competitors
GROUP BY 1;
```

## Disposition

- The decision the mandate asks for is already implemented in the schema, and
  correctly. **No schema change is required or recommended.**
- Do not add competitor columns to `world_benchmark_operating_point`; the
  comparison already has its own view.
- Do not attempt a `CHECK` on either object — both are views.
- The open item is downstream consumer discipline, not storage.

## Boundary

Read-only throughout. No row, column, constraint, view, or grant was created,
altered, or dropped; `evaluation` remains 0 and no measurement field was
written. This note issues no benchmark result and changes no published figure.
