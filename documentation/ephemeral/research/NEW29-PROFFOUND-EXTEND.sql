\set ON_ERROR_STOP on

BEGIN;

DO $guarded_update$
DECLARE
    affected integer;
BEGIN
    UPDATE public.hypotheses
       SET measure_note = concat_ws(
               E'\n\n',
               nullif(measure_note, ''),
               $evidence$[PROF FOUND 2026-08-04]

The committed CUBRIM_PROFILE=1 instrument was re-run on the NEW-29 Silesia corpus rather than the web corpus, using two 2 MiB representative slices. The profiler header's caveat is binding: nested candidates double-count and the table is attribution, not a partition; ordinary wins are running-minimum events. Only FINAL rows answer the final-per-block question.

Measured binary SHA-256: 0a327d55e6d549d4c742a4ca0e098bbc5e02946311893ccddaacc898fd3fd372. Measured source commit: 3a59903910aa526a5d8e1633465f784fbfb4fc65. prof.rs blob SHA-256: 0e6c3eaf2a7b8102df3dcd1837216df4022d662c24e578acd2a4fb58fac727a7. codec.rs blob SHA-256: ff1c27faaae9739c29a40d13582edab43558774961d55e91f2e428edaaf3fa54. Full Silesia manifest SHA-256: d9203058b86b39f94f20b29603a89af5229619b06c78741c64d7098730c39647. Host nproc=16; processes pinned to CPUs 0-3; campaign host 162.55.81.5 untouched.

file | class | full SHA-256 | slice SHA-256 | compressed | ratio | encode wall | decode wall | RT | FINAL
x-ray.2m | image | 7de9fce1405dc44ae5e6813ed21cd5751e761bd4265655a005d39b9685d1c9ad | 9bfd1c5321dbd4dcec1cfb037189ef78ceb7052ce8647086b70b0e1cb401aab3 | 878363 | 0.418836 | 104.518 s | 1.661 s | PASS | geomix 384/384
ooffice.2m | executable | e7ee013880d34dd5208283d0d3d91b07f442e067454276095ded14f322a656eb | 5041e86f07bf17d7a8b3b0ab496a1b6413256399848709f8be543bbdca12de09 | 677605 | 0.323107 | 142.805 s | 23.912 s | PASS | geomix 384/384

Both raw profiler tables contain FINAL:geomix with 384 final blocks and no other FINAL row. Cause is proven for these measured representative image and executable slices: the inner value-scheme rail recomputes a constant final answer. This does not claim all Silesia files, an N=12/N=24 aggregate, or any speed/ratio benefit from a sticky lever. NEW-29 remains closed and its CUBR-0092 KILLED verdict is unchanged. Evidence report and raw tables: documentation/ephemeral/research/CUBR-PROFFOUND-20260804.md and its raw/ directory.$evidence$
           ),
           updated_at = now()
     WHERE id = 'NEW-29'
       AND updated_at = TIMESTAMPTZ '2026-08-02 15:26:18.190543+00'
       AND position('[PROF FOUND 2026-08-04]' in coalesce(measure_note, '')) = 0;

    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN
        RAISE EXCEPTION 'NEW-29 profiler guarded update expected 1 row, changed %', affected;
    END IF;
END
$guarded_update$;

SELECT id,
       status,
       verdict,
       measured,
       measure_date,
       measure_task,
       updated_at,
       length(measure_note) AS measure_note_chars,
       position('[CORPUS CAMPAIGN EXTENSION 2026-08-01]' in measure_note) AS n9_marker_position,
       position('[N=13 SUPERSEDING EXTENSION 2026-08-01]' in measure_note) AS n13_marker_position,
       position('[PROF FOUND 2026-08-04]' in measure_note) AS prof_marker_position
  FROM public.hypotheses
 WHERE id = 'NEW-29';

COMMIT;
