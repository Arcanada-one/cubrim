# Decision: competitor speed at the operating point lives in one labelled view

**Problem (operator-flagged).** `world_benchmark_operating_point` carries
`compress_mib_s` / `decompress_mib_s` for cubrim only (it is defined
`WHERE archiver = 'cubrim'`), so a competitor-speed comparison at the
operating point cannot be drawn from it — yet its column names invite exactly
that read, and the guard was a prose `competitor_note` nobody is forced to
join against the numbers they quote.

**Decision.** Comparisons get a first-class home instead of a convention:

1. `world_benchmark_operating_point` stays cubrim-only. Its view comment and
   the speed columns' comments now state that the columns are cubrim's own
   and that competitor comparisons MUST come from
   `world_benchmark_operating_point_vs_competitors`.
2. New view **`world_benchmark_operating_point_vs_competitors`** is the only
   sanctioned way to read competitor speed at the operating point. Every row
   carries the pairing basis in `competitor_timing_basis`:
   - `same-meta-36` — the `max` preset rows (meta 36): competitors were
     measured in the same Phase C campaign on the same host;
   - `cross-meta-36` — the `balanced` (37) and `web` (38) rows: competitors
     were **not** re-run per preset; the join is cross-meta by design and the
     label rides on the row itself, not in a side note.
   Competitor columns are prefixed `competitor_`, cubrim columns `cubrim_`,
   so a SELECT cannot silently confuse the two.

This implements the mandate's "make it structurally impossible to read the
wrong one": the wrong read (treating the base view's speed columns as a
comparison surface) now dead-ends — the base view has no competitor columns
and its comments point at the comparison view; the right read carries its
own basis label in every row.

## DDL applied (arcana-dbs / `arcanada_cubrim`, 2026-08-09)

```sql
CREATE OR REPLACE VIEW world_benchmark_operating_point_vs_competitors AS
SELECT
  op.meta_id,
  op.preset,
  op.scope,
  op.ratio            AS cubrim_ratio,
  op.file_count,
  op.compress_mib_s   AS cubrim_compress_mib_s,
  op.decompress_mib_s AS cubrim_decompress_mib_s,
  t.archiver          AS competitor,
  a.ratio             AS competitor_ratio,
  t.compress_mib_s    AS competitor_compress_mib_s,
  t.decompress_mib_s  AS competitor_decompress_mib_s,
  CASE WHEN op.meta_id = 36 THEN 'same-meta-36'
       ELSE 'cross-meta-36' END AS competitor_timing_basis,
  op.code_sha,
  op.generated
FROM world_benchmark_operating_point op
JOIN world_benchmark_timing_aggregate t
  ON t.meta_id = 36 AND t.scope = op.scope AND t.archiver <> 'cubrim'
LEFT JOIN world_benchmark_aggregate a
  ON a.meta_id = 36 AND a.scope = op.scope AND a.archiver = t.archiver;

COMMENT ON VIEW world_benchmark_operating_point_vs_competitors IS
  'The ONLY sanctioned surface for competitor comparisons at the operating point. '
  'competitor_timing_basis labels every row: same-meta-36 (preset max shares the '
  'campaign with the competitor pass) or cross-meta-36 (balanced/web pair against '
  'the meta-36 competitor numbers, which were not re-run per preset).';

COMMENT ON VIEW world_benchmark_operating_point IS
  'Cubrim-only operating-point rows. compress_mib_s/decompress_mib_s are CUBRIM''s '
  'own speeds; there are no competitor numbers here. For any competitor comparison '
  'use world_benchmark_operating_point_vs_competitors, which carries the pairing '
  'basis on every row.';

COMMENT ON COLUMN world_benchmark_operating_point.compress_mib_s IS
  'Cubrim''s own compress speed. NOT a comparison surface - see '
  'world_benchmark_operating_point_vs_competitors.';

COMMENT ON COLUMN world_benchmark_operating_point.decompress_mib_s IS
  'Cubrim''s own decompress speed. NOT a comparison surface - see '
  'world_benchmark_operating_point_vs_competitors.';
```

No table data changed; no rows written; `evaluation` untouched. The view is
owner-only (postgres), matching the base view's grants — `cubrim_api_ro` has
no grant on either, so no API surface changed.
