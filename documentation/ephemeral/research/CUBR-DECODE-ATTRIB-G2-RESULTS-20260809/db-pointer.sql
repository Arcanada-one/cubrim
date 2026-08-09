\set ON_ERROR_STOP on

BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SELECT pg_advisory_xact_lock(hashtextextended('NEW-24/decode-attribution-g2-valid-pointer', 0));

SELECT id
FROM hypotheses
WHERE id = 'NEW-24'
FOR UPDATE;

DO $preflight$
DECLARE
    current_row_md5 text;
    marker_count integer;
    note_marker constant text := '[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID]';
    note_suffix constant text := E'\n\n[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID] Valid G2 decode-time characterization completed once on dev-ai with pin 0-15 and landed in PR #66. This is the canonical characterization pointer. Prior PR #54 G0 and PR #58 tier artifacts used the invalid 16-19 path and remain exploratory-only; none of their measurements, verdicts, tier ranking, or lever selection is adopted here. G2 verdicts: P1 and P4 SUPPORTED; P2, P3, and P5 INDETERMINATE. No candidate, benchmark throughput, measurement row, evaluation, or density/speed trade was established. Evidence: documentation/ephemeral/research/CUBR-DECODE-ATTRIB-RESULTS-20260809.md and documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/. NEW-24 remains in_progress.';
BEGIN
    IF current_database() <> 'arcanada_cubrim' THEN
        RAISE EXCEPTION 'wrong database: expected arcanada_cubrim, got %', current_database();
    END IF;

    IF (SELECT system_identifier FROM pg_control_system()) <> 7648390441241305131 THEN
        RAISE EXCEPTION 'wrong PostgreSQL cluster identity';
    END IF;

    IF (SELECT oid FROM pg_database WHERE datname = current_database()) <> 55835 THEN
        RAISE EXCEPTION 'wrong database OID';
    END IF;

    IF current_setting('server_version_num') <> '180004' THEN
        RAISE EXCEPTION 'wrong PostgreSQL server version: %', current_setting('server_version_num');
    END IF;

    IF (SELECT count(*) FROM hypotheses WHERE id = 'NEW-24') <> 1 THEN
        RAISE EXCEPTION 'NEW-24 hypothesis cardinality is not one';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM hypotheses
        WHERE id = 'NEW-24'
          AND status = 'in_progress'
          AND measured IS FALSE
          AND measure_date IS NULL
          AND measure_task IS NULL
          AND value_scheme IS NULL
    ) THEN
        RAISE EXCEPTION 'NEW-24 lifecycle boundary changed';
    END IF;

    IF (SELECT count(*) FROM measurements WHERE hypothesis_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 measurements are not empty';
    END IF;

    IF (SELECT count(*)
        FROM web_benchmark_hypothesis_evaluation e
        JOIN web_benchmark_hypothesis h ON h.id = e.hypothesis_id
        WHERE h.task_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 evaluation is not zero';
    END IF;

    IF (SELECT count(*) FROM web_benchmark_hypothesis WHERE task_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 unexpectedly has a web benchmark hypothesis row';
    END IF;

    SELECT md5(to_jsonb(h)::text),
           (length(coalesce(measure_note, '')) - length(replace(coalesce(measure_note, ''), note_marker, ''))) / length(note_marker)
    INTO STRICT current_row_md5, marker_count
    FROM hypotheses h
    WHERE id = 'NEW-24';

    IF marker_count = 0 THEN
        IF current_row_md5 <> '0cea632fb56f94646f0876f559e61817' THEN
            RAISE EXCEPTION 'NEW-24 pre-state changed: expected row md5 %, got %',
                '0cea632fb56f94646f0876f559e61817', current_row_md5;
        END IF;
    ELSIF marker_count = 1 THEN
        IF right((SELECT measure_note FROM hypotheses WHERE id = 'NEW-24'), length(note_suffix)) <> note_suffix THEN
            RAISE EXCEPTION 'NEW-24 canonical marker exists with conflicting content';
        END IF;
    ELSE
        RAISE EXCEPTION 'NEW-24 canonical marker count is %, expected 0 or 1', marker_count;
    END IF;
END
$preflight$;

UPDATE hypotheses
SET measure_note = coalesce(measure_note, '') || E'\n\n[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID] Valid G2 decode-time characterization completed once on dev-ai with pin 0-15 and landed in PR #66. This is the canonical characterization pointer. Prior PR #54 G0 and PR #58 tier artifacts used the invalid 16-19 path and remain exploratory-only; none of their measurements, verdicts, tier ranking, or lever selection is adopted here. G2 verdicts: P1 and P4 SUPPORTED; P2, P3, and P5 INDETERMINATE. No candidate, benchmark throughput, measurement row, evaluation, or density/speed trade was established. Evidence: documentation/ephemeral/research/CUBR-DECODE-ATTRIB-RESULTS-20260809.md and documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/. NEW-24 remains in_progress.',
    updated_at = now()
WHERE id = 'NEW-24'
  AND strpos(coalesce(measure_note, ''), '[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID]') = 0;

DO $postcondition$
DECLARE
    marker_count integer;
    note_marker constant text := '[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID]';
    note_suffix constant text := E'\n\n[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID] Valid G2 decode-time characterization completed once on dev-ai with pin 0-15 and landed in PR #66. This is the canonical characterization pointer. Prior PR #54 G0 and PR #58 tier artifacts used the invalid 16-19 path and remain exploratory-only; none of their measurements, verdicts, tier ranking, or lever selection is adopted here. G2 verdicts: P1 and P4 SUPPORTED; P2, P3, and P5 INDETERMINATE. No candidate, benchmark throughput, measurement row, evaluation, or density/speed trade was established. Evidence: documentation/ephemeral/research/CUBR-DECODE-ATTRIB-RESULTS-20260809.md and documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/. NEW-24 remains in_progress.';
BEGIN
    SELECT (length(coalesce(measure_note, '')) - length(replace(coalesce(measure_note, ''), note_marker, ''))) / length(note_marker)
    INTO STRICT marker_count
    FROM hypotheses
    WHERE id = 'NEW-24';

    IF marker_count <> 1
       OR right((SELECT measure_note FROM hypotheses WHERE id = 'NEW-24'), length(note_suffix)) <> note_suffix THEN
        RAISE EXCEPTION 'NEW-24 canonical pointer postcondition failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM hypotheses
        WHERE id = 'NEW-24'
          AND status = 'in_progress'
          AND measured IS FALSE
          AND measure_date IS NULL
          AND measure_task IS NULL
          AND value_scheme IS NULL
    ) THEN
        RAISE EXCEPTION 'NEW-24 lifecycle boundary changed after pointer update';
    END IF;

    IF (SELECT count(*) FROM measurements WHERE hypothesis_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 measurements changed during pointer transaction';
    END IF;

    IF (SELECT count(*)
        FROM web_benchmark_hypothesis_evaluation e
        JOIN web_benchmark_hypothesis h ON h.id = e.hypothesis_id
        WHERE h.task_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 evaluation changed during pointer transaction';
    END IF;

    IF (SELECT count(*) FROM web_benchmark_hypothesis WHERE task_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 web benchmark hypothesis changed during pointer transaction';
    END IF;
END
$postcondition$;

WITH expected AS (
    SELECT
        '[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID]'::text AS note_marker,
        E'\n\n[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID] Valid G2 decode-time characterization completed once on dev-ai with pin 0-15 and landed in PR #66. This is the canonical characterization pointer. Prior PR #54 G0 and PR #58 tier artifacts used the invalid 16-19 path and remain exploratory-only; none of their measurements, verdicts, tier ranking, or lever selection is adopted here. G2 verdicts: P1 and P4 SUPPORTED; P2, P3, and P5 INDETERMINATE. No candidate, benchmark throughput, measurement row, evaluation, or density/speed trade was established. Evidence: documentation/ephemeral/research/CUBR-DECODE-ATTRIB-RESULTS-20260809.md and documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/. NEW-24 remains in_progress.'::text AS note_suffix
)
SELECT id,
       status,
       measured,
       measure_date,
       measure_task,
       value_scheme,
       updated_at,
       md5(to_jsonb(h)::text) AS row_md5,
       md5(coalesce(measure_note, '')) AS measure_note_md5,
       length(coalesce(measure_note, '')) AS measure_note_length,
       (length(measure_note) - length(replace(measure_note, expected.note_marker, ''))) / length(expected.note_marker) AS canonical_marker_count,
       right(measure_note, length(expected.note_suffix)) = expected.note_suffix AS canonical_suffix_exact,
       md5(right(measure_note, length(expected.note_suffix))) AS canonical_suffix_md5,
       md5(expected.note_suffix) AS expected_suffix_md5
FROM hypotheses h
CROSS JOIN expected
WHERE id = 'NEW-24';

SELECT count(*) AS measurement_count
FROM measurements
WHERE hypothesis_id = 'NEW-24';

SELECT count(*) AS evaluation_count
FROM web_benchmark_hypothesis_evaluation e
JOIN web_benchmark_hypothesis h ON h.id = e.hypothesis_id
WHERE h.task_id = 'NEW-24';

SELECT count(*) AS web_benchmark_hypothesis_count
FROM web_benchmark_hypothesis
WHERE task_id = 'NEW-24';

COMMIT;
