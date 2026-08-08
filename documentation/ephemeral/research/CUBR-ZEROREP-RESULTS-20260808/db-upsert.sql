\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SELECT pg_advisory_xact_lock(hashtext('NEW-30/zerorep-nci-max-pin0-15-t4'));

DO $preflight$
DECLARE
    measurement_count integer;
    note_suffix constant text := E'\n\n[EXTENSION 2026-08-08 · CUBR-ZEROREP] Preregistered nci/max zero-representation run completed under systemd with result=success/exit 0, admission loadavg 0.16, pin 0-15, threads 4, one warmup and three interleaved decode samples per build. All three 104139-byte archives matched canonical sha256 1dcc11fa179e3aa0a0b745fba85b5c2187aa382b4b3022ec8ecd8839962b925b and all nine round trips passed. Medians: pre-PR41 18.71 s / 1430016 KiB; current packed 15.61 s / 1710592 KiB; zero-rep 15.25 s / 998912 KiB. Zero-rep reclaimed 711680 KiB (695 MiB), 253.65% of the same-run packed penalty and 90.49% of the 768 MiB ceiling; residual versus pre-PR41 was -431104 KiB. Zero/current time ratio 0.97694; pre-PR41/zero speedup 1.22689x. Compound prediction PASS. Public evidence: documentation/ephemeral/research/CUBR-ZEROREP-RESULTS-20260808/. Evaluation remains untouched (0).';
BEGIN
    IF (SELECT count(*) FROM hypotheses WHERE id = 'NEW-30') <> 1 THEN
        RAISE EXCEPTION 'NEW-30 hypothesis cardinality is not one';
    END IF;

    IF (SELECT count(*)
        FROM web_benchmark_hypothesis_evaluation e
        JOIN web_benchmark_hypothesis h ON h.id = e.hypothesis_id
        WHERE h.task_id = 'NEW-30') <> 0 THEN
        RAISE EXCEPTION 'NEW-30 evaluation is not zero';
    END IF;

    SELECT count(*) INTO measurement_count
    FROM measurements
    WHERE hypothesis_id = 'NEW-30'
      AND run_mode = 'zerorep-nci-max-pin0-15-t4';

    IF measurement_count NOT IN (0, 3) THEN
        RAISE EXCEPTION 'partial/conflicting run-mode state: % rows', measurement_count;
    END IF;

    IF measurement_count = 0
       AND right((SELECT measure_note FROM hypotheses WHERE id = 'NEW-30'), length(note_suffix)) = note_suffix THEN
        RAISE EXCEPTION 'note exists without the three measurement rows';
    END IF;
END
$preflight$;

INSERT INTO codec_revisions (sha, label, built_at, host)
VALUES (
    'cli-sha256:771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20',
    'zero-representation packed Ctr build (src commit f047523fcdc15561baa05fee597819fd6bdb53d3; cm2.rs sha256 1594578cc98f4ef55ae102cbe31fc5cdde02d6c647941787cc009464abe8addf; fresh clean checkout built on dev-ai with rustc 1.96.1)',
    '2026-08-08 13:23:43.945119627+00',
    'dev-ai/100.118.134.82 (built and measured; AMD EPYC 7502P)'
)
ON CONFLICT (sha) DO NOTHING;

UPDATE hypotheses
SET measure_task = measure_task || '; zero-representation nci/max extension 2026-08-08 (zerorep.tsv)',
    measure_note = measure_note || E'\n\n[EXTENSION 2026-08-08 · CUBR-ZEROREP] Preregistered nci/max zero-representation run completed under systemd with result=success/exit 0, admission loadavg 0.16, pin 0-15, threads 4, one warmup and three interleaved decode samples per build. All three 104139-byte archives matched canonical sha256 1dcc11fa179e3aa0a0b745fba85b5c2187aa382b4b3022ec8ecd8839962b925b and all nine round trips passed. Medians: pre-PR41 18.71 s / 1430016 KiB; current packed 15.61 s / 1710592 KiB; zero-rep 15.25 s / 998912 KiB. Zero-rep reclaimed 711680 KiB (695 MiB), 253.65% of the same-run packed penalty and 90.49% of the 768 MiB ceiling; residual versus pre-PR41 was -431104 KiB. Zero/current time ratio 0.97694; pre-PR41/zero speedup 1.22689x. Compound prediction PASS. Public evidence: documentation/ephemeral/research/CUBR-ZEROREP-RESULTS-20260808/. Evaluation remains untouched (0).',
    updated_at = now()
WHERE id = 'NEW-30'
  AND NOT EXISTS (
      SELECT 1 FROM measurements
      WHERE hypothesis_id = 'NEW-30'
        AND run_mode = 'zerorep-nci-max-pin0-15-t4'
  );

WITH expected(sha, decode_ms, decode_rss) AS (
    VALUES
        ('cli-sha256:a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd', 18710, 1430016::bigint),
        ('cli-sha256:12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c', 15610, 1710592::bigint),
        ('cli-sha256:771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20', 15250, 998912::bigint)
)
INSERT INTO measurements (
    hypothesis_id, codec_rev, corpus_file, run_mode,
    orig_bytes, comp_bytes, ratio, rt_ok,
    duration_ms, measured_at, peak_rss_kib,
    decode_ms, decode_peak_rss_kib, host, cpu_pin
)
SELECT
    'NEW-30', r.id, 'silesia/nci[0:2097152]', 'zerorep-nci-max-pin0-15-t4',
    2097152, 104139, 0.049657344818115234, true,
    NULL, '2026-08-08 13:48:21+00', NULL,
    e.decode_ms, e.decode_rss, 'dev-ai', '0-15'
FROM expected e
JOIN codec_revisions r ON r.sha = e.sha
WHERE NOT EXISTS (
    SELECT 1 FROM measurements
    WHERE hypothesis_id = 'NEW-30'
      AND run_mode = 'zerorep-nci-max-pin0-15-t4'
);

DO $assertions$
DECLARE
    row_count integer;
    revision_count integer;
    exact_count integer;
    note_suffix constant text := E'\n\n[EXTENSION 2026-08-08 · CUBR-ZEROREP] Preregistered nci/max zero-representation run completed under systemd with result=success/exit 0, admission loadavg 0.16, pin 0-15, threads 4, one warmup and three interleaved decode samples per build. All three 104139-byte archives matched canonical sha256 1dcc11fa179e3aa0a0b745fba85b5c2187aa382b4b3022ec8ecd8839962b925b and all nine round trips passed. Medians: pre-PR41 18.71 s / 1430016 KiB; current packed 15.61 s / 1710592 KiB; zero-rep 15.25 s / 998912 KiB. Zero-rep reclaimed 711680 KiB (695 MiB), 253.65% of the same-run packed penalty and 90.49% of the 768 MiB ceiling; residual versus pre-PR41 was -431104 KiB. Zero/current time ratio 0.97694; pre-PR41/zero speedup 1.22689x. Compound prediction PASS. Public evidence: documentation/ephemeral/research/CUBR-ZEROREP-RESULTS-20260808/. Evaluation remains untouched (0).';
BEGIN
    SELECT count(*), count(DISTINCT codec_rev) INTO row_count, revision_count
    FROM measurements
    WHERE hypothesis_id = 'NEW-30'
      AND run_mode = 'zerorep-nci-max-pin0-15-t4';

    SELECT count(*) INTO exact_count
    FROM measurements m
    JOIN codec_revisions r ON r.id = m.codec_rev
    WHERE m.hypothesis_id = 'NEW-30'
      AND m.run_mode = 'zerorep-nci-max-pin0-15-t4'
      AND m.corpus_file = 'silesia/nci[0:2097152]'
      AND m.orig_bytes = 2097152
      AND m.comp_bytes = 104139
      AND m.ratio = 0.049657344818115234
      AND m.rt_ok
      AND m.duration_ms IS NULL
      AND m.peak_rss_kib IS NULL
      AND m.decode_ms IS NOT NULL
      AND m.decode_peak_rss_kib IS NOT NULL
      AND m.measured_at = '2026-08-08 13:48:21+00'
      AND m.host = 'dev-ai'
      AND m.cpu_pin = '0-15'
      AND (
          (r.sha = 'cli-sha256:a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd' AND m.decode_ms = 18710 AND m.decode_peak_rss_kib = 1430016)
          OR (r.sha = 'cli-sha256:12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c' AND m.decode_ms = 15610 AND m.decode_peak_rss_kib = 1710592)
          OR (r.sha = 'cli-sha256:771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20' AND m.decode_ms = 15250 AND m.decode_peak_rss_kib = 998912)
      );

    IF row_count <> 3 OR revision_count <> 3 OR exact_count <> 3 THEN
        RAISE EXCEPTION 'measurement assertions failed: rows %, revisions %, exact %', row_count, revision_count, exact_count;
    END IF;

    IF (SELECT count(*)
        FROM codec_revisions
        WHERE sha = 'cli-sha256:771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20'
          AND label = 'zero-representation packed Ctr build (src commit f047523fcdc15561baa05fee597819fd6bdb53d3; cm2.rs sha256 1594578cc98f4ef55ae102cbe31fc5cdde02d6c647941787cc009464abe8addf; fresh clean checkout built on dev-ai with rustc 1.96.1)'
          AND built_at = '2026-08-08 13:23:43.945119627+00'
          AND host = 'dev-ai/100.118.134.82 (built and measured; AMD EPYC 7502P)') <> 1 THEN
        RAISE EXCEPTION 'zero-representation codec revision conflicts with expected identity';
    END IF;

    IF right((SELECT measure_note FROM hypotheses WHERE id = 'NEW-30'), length(note_suffix)) <> note_suffix THEN
        RAISE EXCEPTION 'NEW-30 note suffix is missing or conflicting';
    END IF;

    IF (SELECT count(*)
        FROM web_benchmark_hypothesis_evaluation e
        JOIN web_benchmark_hypothesis h ON h.id = e.hypothesis_id
        WHERE h.task_id = 'NEW-30') <> 0 THEN
        RAISE EXCEPTION 'NEW-30 evaluation changed';
    END IF;
END
$assertions$;

SELECT 'transaction_rows', count(*), count(DISTINCT codec_rev)
FROM measurements
WHERE hypothesis_id = 'NEW-30'
  AND run_mode = 'zerorep-nci-max-pin0-15-t4';

COMMIT;
