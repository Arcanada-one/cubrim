\set ON_ERROR_STOP on

-- Manual recovery only. This restores precisely the two columns changed by
-- db-pointer.sql to their backed-up values. It intentionally refuses any
-- state other than the exact canonical suffix and untouched lifecycle gates.
BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SELECT pg_advisory_xact_lock(hashtextextended('NEW-24/decode-attribution-g2-valid-pointer', 0));

DO $restore_preflight$
DECLARE
    current_row_md5 text;
    current_note text;
    old_note constant text := $old_note$не реализовано — GO (флагман): MODE_CM (logistic mixing+SSE) = реализация NEW-01/H-61 backend-lever | 2026-08-09: decode-attribution characterisation preregistered (PR #51, main d212c1c) and running on dev-ai — groundwork before any Fast-CM lever. | 2026-08-09 MEASURED (characterisation, PR #54): decode budget on CM2 cells = ~50% probe-load latency (predict_bit), ~33% Ctr::upd write-back, ~7% mixer/APM update, 0.45-0.59% range coder; IPC 1.46-1.89, single-threaded; max->web speedup entirely reduced memory stalling. Compound lever = fewer models per bit (time-budgeted selection) — SIMD/rANS directions dead at <=1.005-1.1x. x-ray decode 98% geocm, 0% CM2.$old_note$;
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
        SELECT 1 FROM hypotheses
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

    SELECT md5(to_jsonb(h)::text), measure_note
    INTO STRICT current_row_md5, current_note
    FROM hypotheses h
    WHERE id = 'NEW-24';

    IF current_row_md5 = '5225fa156218ce15b2a420b98651b4eb' THEN
        IF current_note <> old_note || note_suffix THEN
            RAISE EXCEPTION 'NEW-24 applied row has a conflicting note prefix or suffix';
        END IF;
    ELSIF current_row_md5 = '0cea632fb56f94646f0876f559e61817' THEN
        IF current_note <> old_note THEN
            RAISE EXCEPTION 'NEW-24 backed-up row has conflicting note content';
        END IF;
    ELSE
        RAISE EXCEPTION 'NEW-24 restore source row changed: got md5 %', current_row_md5;
    END IF;
END
$restore_preflight$;

UPDATE hypotheses
SET measure_note = $old_note$не реализовано — GO (флагман): MODE_CM (logistic mixing+SSE) = реализация NEW-01/H-61 backend-lever | 2026-08-09: decode-attribution characterisation preregistered (PR #51, main d212c1c) and running on dev-ai — groundwork before any Fast-CM lever. | 2026-08-09 MEASURED (characterisation, PR #54): decode budget on CM2 cells = ~50% probe-load latency (predict_bit), ~33% Ctr::upd write-back, ~7% mixer/APM update, 0.45-0.59% range coder; IPC 1.46-1.89, single-threaded; max->web speedup entirely reduced memory stalling. Compound lever = fewer models per bit (time-budgeted selection) — SIMD/rANS directions dead at <=1.005-1.1x. x-ray decode 98% geocm, 0% CM2.$old_note$,
    updated_at = '2026-08-09 13:17:57.883153+00'
WHERE id = 'NEW-24'
  AND status = 'in_progress'
  AND measured IS FALSE
  AND measure_date IS NULL
  AND measure_task IS NULL
  AND value_scheme IS NULL
  AND md5(to_jsonb(hypotheses)::text) = '5225fa156218ce15b2a420b98651b4eb'
  AND measure_note = $old_note$не реализовано — GO (флагман): MODE_CM (logistic mixing+SSE) = реализация NEW-01/H-61 backend-lever | 2026-08-09: decode-attribution characterisation preregistered (PR #51, main d212c1c) and running on dev-ai — groundwork before any Fast-CM lever. | 2026-08-09 MEASURED (characterisation, PR #54): decode budget on CM2 cells = ~50% probe-load latency (predict_bit), ~33% Ctr::upd write-back, ~7% mixer/APM update, 0.45-0.59% range coder; IPC 1.46-1.89, single-threaded; max->web speedup entirely reduced memory stalling. Compound lever = fewer models per bit (time-budgeted selection) — SIMD/rANS directions dead at <=1.005-1.1x. x-ray decode 98% geocm, 0% CM2.$old_note$ || E'\n\n[EXTENSION 2026-08-09 · CUBR-DECODE-ATTRIB-G2-VALID] Valid G2 decode-time characterization completed once on dev-ai with pin 0-15 and landed in PR #66. This is the canonical characterization pointer. Prior PR #54 G0 and PR #58 tier artifacts used the invalid 16-19 path and remain exploratory-only; none of their measurements, verdicts, tier ranking, or lever selection is adopted here. G2 verdicts: P1 and P4 SUPPORTED; P2, P3, and P5 INDETERMINATE. No candidate, benchmark throughput, measurement row, evaluation, or density/speed trade was established. Evidence: documentation/ephemeral/research/CUBR-DECODE-ATTRIB-RESULTS-20260809.md and documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/. NEW-24 remains in_progress.';

DO $assert_restore$
BEGIN
    IF (SELECT count(*) FROM hypotheses WHERE id = 'NEW-24' AND md5(to_jsonb(hypotheses)::text) = '0cea632fb56f94646f0876f559e61817') <> 1 THEN
        RAISE EXCEPTION 'NEW-24 restore did not reproduce the backed-up row';
    END IF;
    IF (SELECT count(*) FROM measurements WHERE hypothesis_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 measurement boundary changed';
    END IF;
    IF (SELECT count(*)
        FROM web_benchmark_hypothesis_evaluation e
        JOIN web_benchmark_hypothesis h ON h.id = e.hypothesis_id
        WHERE h.task_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 evaluation boundary changed';
    END IF;
    IF (SELECT count(*) FROM web_benchmark_hypothesis WHERE task_id = 'NEW-24') <> 0 THEN
        RAISE EXCEPTION 'NEW-24 web benchmark hypothesis boundary changed';
    END IF;
END
$assert_restore$;

COMMIT;
