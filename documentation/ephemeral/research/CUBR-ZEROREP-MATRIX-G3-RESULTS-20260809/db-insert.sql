\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SELECT pg_advisory_xact_lock(hashtext('NEW-30/zerorep-matrix-g3-pin0-15-t4'));

LOCK TABLE measurements,
           hypotheses,
           codec_revisions,
           web_benchmark_hypothesis,
           web_benchmark_hypothesis_evaluation
IN SHARE ROW EXCLUSIVE MODE;

CREATE TEMPORARY TABLE frozen_new30_snapshot ON COMMIT DROP AS
SELECT $snapshot$[{"id": 389, "host": "dev-ai", "ratio": 0.220032, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "levers-wall-pin0-15-t4", "codec_rev": 7, "decode_ms": 26430, "comp_bytes": 461437, "orig_bytes": 2097152, "corpus_file": "silesia/dickens[0:2097152]", "duration_ms": 78450, "measured_at": "2026-08-08T05:07:00+00:00", "peak_rss_kib": 1631360, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1543680}, {"id": 390, "host": "dev-ai", "ratio": 0.220032, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "levers-wall-pin0-15-t4", "codec_rev": 8, "decode_ms": 19910, "comp_bytes": 461437, "orig_bytes": 2097152, "corpus_file": "silesia/dickens[0:2097152]", "duration_ms": 59570, "measured_at": "2026-08-08T05:07:00+00:00", "peak_rss_kib": 1812908, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1719808}, {"id": 391, "host": "dev-ai", "ratio": 0.049658, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "levers-wall-pin0-15-t4", "codec_rev": 7, "decode_ms": 18050, "comp_bytes": 104139, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": 116740, "measured_at": "2026-08-08T05:07:00+00:00", "peak_rss_kib": 1721868, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1429504}, {"id": 392, "host": "dev-ai", "ratio": 0.049658, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "levers-wall-pin0-15-t4", "codec_rev": 8, "decode_ms": 15620, "comp_bytes": 104139, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": 111250, "measured_at": "2026-08-08T05:07:00+00:00", "peak_rss_kib": 1863676, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1709568}, {"id": 393, "host": "dev-ai", "ratio": 0.323107, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "levers-wall-pin0-15-t4", "codec_rev": 7, "decode_ms": 25020, "comp_bytes": 677605, "orig_bytes": 2097152, "corpus_file": "silesia/ooffice[0:2097152]", "duration_ms": 122000, "measured_at": "2026-08-08T05:07:00+00:00", "peak_rss_kib": 1858580, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1634816}, {"id": 394, "host": "dev-ai", "ratio": 0.323107, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "levers-wall-pin0-15-t4", "codec_rev": 8, "decode_ms": 19060, "comp_bytes": 677605, "orig_bytes": 2097152, "corpus_file": "silesia/ooffice[0:2097152]", "duration_ms": 110870, "measured_at": "2026-08-08T05:07:00+00:00", "peak_rss_kib": 1938700, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1707520}, {"id": 395, "host": "dev-ai", "ratio": 0.2200303077697754, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-max-pin0-15-t4", "codec_rev": 9, "decode_ms": 27030, "comp_bytes": 461437, "orig_bytes": 2097152, "corpus_file": "silesia/dickens[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1543680}, {"id": 396, "host": "dev-ai", "ratio": 0.2200303077697754, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-max-pin0-15-t4", "codec_rev": 8, "decode_ms": 20000, "comp_bytes": 461437, "orig_bytes": 2097152, "corpus_file": "silesia/dickens[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1719808}, {"id": 397, "host": "dev-ai", "ratio": 0.2251877784729004, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-balanced-pin0-15-t4", "codec_rev": 9, "decode_ms": 25870, "comp_bytes": 472253, "orig_bytes": 2097152, "corpus_file": "silesia/dickens[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1486336}, {"id": 398, "host": "dev-ai", "ratio": 0.2251877784729004, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-balanced-pin0-15-t4", "codec_rev": 8, "decode_ms": 19240, "comp_bytes": 472253, "orig_bytes": 2097152, "corpus_file": "silesia/dickens[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1654784}, {"id": 399, "host": "dev-ai", "ratio": 0.23246097564697266, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-web-pin0-15-t4", "codec_rev": 9, "decode_ms": 22550, "comp_bytes": 487506, "orig_bytes": 2097152, "corpus_file": "silesia/dickens[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 110080}, {"id": 400, "host": "dev-ai", "ratio": 0.23246097564697266, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-web-pin0-15-t4", "codec_rev": 8, "decode_ms": 17220, "comp_bytes": 487506, "orig_bytes": 2097152, "corpus_file": "silesia/dickens[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 113152}, {"id": 401, "host": "dev-ai", "ratio": 0.049657344818115234, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-max-pin0-15-t4", "codec_rev": 9, "decode_ms": 18760, "comp_bytes": 104139, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1430016}, {"id": 402, "host": "dev-ai", "ratio": 0.049657344818115234, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-max-pin0-15-t4", "codec_rev": 8, "decode_ms": 15700, "comp_bytes": 104139, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1710080}, {"id": 403, "host": "dev-ai", "ratio": 0.051505088806152344, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-balanced-pin0-15-t4", "codec_rev": 9, "decode_ms": 18070, "comp_bytes": 108014, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1385984}, {"id": 404, "host": "dev-ai", "ratio": 0.051505088806152344, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-balanced-pin0-15-t4", "codec_rev": 8, "decode_ms": 15090, "comp_bytes": 108014, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1644544}, {"id": 405, "host": "dev-ai", "ratio": 0.05179595947265625, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-web-pin0-15-t4", "codec_rev": 9, "decode_ms": 15750, "comp_bytes": 108624, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 107520}, {"id": 406, "host": "dev-ai", "ratio": 0.05179595947265625, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-web-pin0-15-t4", "codec_rev": 8, "decode_ms": 13410, "comp_bytes": 108624, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 111616}, {"id": 407, "host": "dev-ai", "ratio": 0.3231072425842285, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-max-pin0-15-t4", "codec_rev": 9, "decode_ms": 25580, "comp_bytes": 677605, "orig_bytes": 2097152, "corpus_file": "silesia/ooffice[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1635328}, {"id": 408, "host": "dev-ai", "ratio": 0.3231072425842285, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-max-pin0-15-t4", "codec_rev": 8, "decode_ms": 18990, "comp_bytes": 677605, "orig_bytes": 2097152, "corpus_file": "silesia/ooffice[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1708544}, {"id": 409, "host": "dev-ai", "ratio": 0.3231072425842285, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-balanced-pin0-15-t4", "codec_rev": 9, "decode_ms": 25400, "comp_bytes": 677605, "orig_bytes": 2097152, "corpus_file": "silesia/ooffice[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1635840}, {"id": 410, "host": "dev-ai", "ratio": 0.3231072425842285, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-balanced-pin0-15-t4", "codec_rev": 8, "decode_ms": 18950, "comp_bytes": 677605, "orig_bytes": 2097152, "corpus_file": "silesia/ooffice[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1708032}, {"id": 411, "host": "dev-ai", "ratio": 0.33573484420776367, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-web-pin0-15-t4", "codec_rev": 9, "decode_ms": 22240, "comp_bytes": 704087, "orig_bytes": 2097152, "corpus_file": "silesia/ooffice[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 112640}, {"id": 412, "host": "dev-ai", "ratio": 0.33573484420776367, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "preset-rss-web-pin0-15-t4", "codec_rev": 8, "decode_ms": 16930, "comp_bytes": 704087, "orig_bytes": 2097152, "corpus_file": "silesia/ooffice[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T09:15:13+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 115200}, {"id": 413, "host": "dev-ai", "ratio": 0.049657344818115234, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "zerorep-nci-max-pin0-15-t4", "codec_rev": 8, "decode_ms": 15610, "comp_bytes": 104139, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T13:48:21+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1710592}, {"id": 414, "host": "dev-ai", "ratio": 0.049657344818115234, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "zerorep-nci-max-pin0-15-t4", "codec_rev": 9, "decode_ms": 18710, "comp_bytes": 104139, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T13:48:21+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 1430016}, {"id": 415, "host": "dev-ai", "ratio": 0.049657344818115234, "rt_ok": true, "cpu_pin": "0-15", "run_mode": "zerorep-nci-max-pin0-15-t4", "codec_rev": 10, "decode_ms": 15250, "comp_bytes": 104139, "orig_bytes": 2097152, "corpus_file": "silesia/nci[0:2097152]", "duration_ms": null, "measured_at": "2026-08-08T13:48:21+00:00", "peak_rss_kib": null, "hypothesis_id": "NEW-30", "decode_peak_rss_kib": 998912}]$snapshot$::jsonb AS rows;

DO $preflight$
DECLARE
    total_count integer;
    total_mode_count integer;
    matrix_count integer;
    matrix_mode_count integer;
    revision_count integer;
    exact_count integer;
    marker_count integer;
    frozen_existing jsonb;
    current_existing jsonb;
    note_marker constant text := '[EXTENSION 2026-08-09 · CUBR-ZEROREP-MATRIX-G3]';
    note_suffix constant text := E'\n\n[EXTENSION 2026-08-09 · CUBR-ZEROREP-MATRIX-G3] Preregistered eight-cell zero-representation matrix completed under systemd with result=success/exit 0, pin 0-15, threads 4, one warmup and three interleaved decode samples per build. Cell verdicts: nci/balanced=PASS/ACCOUNTING_CONSISTENT; nci/web=PASS/ACCOUNTING_CONSISTENT; dickens/max=PASS/ACCOUNTING_CONSISTENT; dickens/balanced=PASS/ACCOUNTING_CONSISTENT; dickens/web=PASS/ACCOUNTING_CONSISTENT; ooffice/max=PASS/ACCOUNTING_CONSISTENT; ooffice/balanced=PASS/ACCOUNTING_CONSISTENT; ooffice/web=PASS/ACCOUNTING_CONSISTENT. All 24 canonical archives and all 96 round trips passed. Evidence: documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-RESULTS-20260809/. Evaluation remains untouched (0).';
BEGIN
    IF (SELECT system_identifier FROM pg_control_system()) <> 7648390441241305131 THEN
        RAISE EXCEPTION 'wrong PostgreSQL cluster identity';
    END IF;

    IF (SELECT oid FROM pg_database WHERE datname = current_database()) <> 55835 THEN
        RAISE EXCEPTION 'wrong database OID';
    END IF;

    IF current_setting('server_version_num') <> '180004' THEN
        RAISE EXCEPTION 'wrong PostgreSQL server version: %', current_setting('server_version_num');
    END IF;

    SELECT rows INTO STRICT frozen_existing
    FROM frozen_new30_snapshot;

    SELECT jsonb_agg(to_jsonb(m) ORDER BY id)
    INTO current_existing
    FROM measurements m
    WHERE hypothesis_id = 'NEW-30'
      AND run_mode NOT IN (
          'zerorep-nci-balanced-pin0-15-t4',
          'zerorep-nci-web-pin0-15-t4',
          'zerorep-dickens-max-pin0-15-t4',
          'zerorep-dickens-balanced-pin0-15-t4',
          'zerorep-dickens-web-pin0-15-t4',
          'zerorep-ooffice-max-pin0-15-t4',
          'zerorep-ooffice-balanced-pin0-15-t4',
          'zerorep-ooffice-web-pin0-15-t4'
      );

    IF current_existing IS DISTINCT FROM frozen_existing THEN
        RAISE EXCEPTION 'preexisting NEW-30 measurement snapshot changed';
    END IF;

    IF current_database() <> 'arcanada_cubrim' THEN
        RAISE EXCEPTION 'wrong database: expected arcanada_cubrim, got %', current_database();
    END IF;

    IF (SELECT count(*) FROM hypotheses WHERE id = 'NEW-30') <> 1 THEN
        RAISE EXCEPTION 'NEW-30 hypothesis cardinality is not one';
    END IF;

    IF (SELECT count(*)
        FROM web_benchmark_hypothesis_evaluation e
        JOIN web_benchmark_hypothesis h ON h.id = e.hypothesis_id
        WHERE h.task_id = 'NEW-30') <> 0 THEN
        RAISE EXCEPTION 'NEW-30 evaluation is not zero';
    END IF;

    IF (SELECT count(*)
        FROM codec_revisions
        WHERE (id = 9 AND sha = 'cli-sha256:a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd')
           OR (id = 8 AND sha = 'cli-sha256:12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c')
           OR (id = 10 AND sha = 'cli-sha256:771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20')) <> 3 THEN
        RAISE EXCEPTION 'codec revision IDs 9/8/10 do not match the frozen base/current/zero identities';
    END IF;

    SELECT count(*), count(DISTINCT run_mode)
    INTO total_count, total_mode_count
    FROM measurements
    WHERE hypothesis_id = 'NEW-30';

    SELECT count(*), count(DISTINCT run_mode), count(DISTINCT codec_rev)
    INTO matrix_count, matrix_mode_count, revision_count
    FROM measurements
    WHERE hypothesis_id = 'NEW-30'
      AND run_mode IN (
          'zerorep-nci-balanced-pin0-15-t4',
          'zerorep-nci-web-pin0-15-t4',
          'zerorep-dickens-max-pin0-15-t4',
          'zerorep-dickens-balanced-pin0-15-t4',
          'zerorep-dickens-web-pin0-15-t4',
          'zerorep-ooffice-max-pin0-15-t4',
          'zerorep-ooffice-balanced-pin0-15-t4',
          'zerorep-ooffice-web-pin0-15-t4'
      );

    SELECT (length(coalesce(measure_note, '')) - length(replace(coalesce(measure_note, ''), note_marker, ''))) / length(note_marker)
    INTO marker_count
    FROM hypotheses
    WHERE id = 'NEW-30';

    WITH cells(file_name, preset, comp_bytes, base_ms, base_rss, current_ms, current_rss, zero_ms, zero_rss) AS (
        VALUES
            ('nci', 'balanced', 108014, 18170, 1385472::bigint, 15070, 1645056::bigint, 14680, 991744::bigint),
            ('nci', 'web', 108624, 15770, 108032::bigint, 13390, 111616::bigint, 13080, 92672::bigint),
            ('dickens', 'max', 461437, 26940, 1543680::bigint, 19950, 1719808::bigint, 20060, 1154560::bigint),
            ('dickens', 'balanced', 472253, 25710, 1486848::bigint, 19250, 1654272::bigint, 19330, 1135104::bigint),
            ('dickens', 'web', 487506, 22540, 110080::bigint, 17170, 113152::bigint, 17080, 104960::bigint),
            ('ooffice', 'max', 677605, 25530, 1635328::bigint, 19080, 1708544::bigint, 19210, 1474048::bigint),
            ('ooffice', 'balanced', 677605, 25540, 1635328::bigint, 19070, 1708032::bigint, 19340, 1474048::bigint),
            ('ooffice', 'web', 704087, 22290, 112640::bigint, 17120, 115200::bigint, 16800, 108032::bigint)
    ),
    expected AS (
        SELECT
            'zerorep-' || c.file_name || '-' || c.preset || '-pin0-15-t4' AS run_mode,
            'silesia/' || c.file_name || '[0:2097152]' AS corpus_file,
            2097152::bigint AS orig_bytes,
            c.comp_bytes::bigint AS comp_bytes,
            r.codec_rev,
            r.decode_ms,
            r.decode_rss
        FROM cells c
        CROSS JOIN LATERAL (
            VALUES
                (9, c.base_ms, c.base_rss),
                (8, c.current_ms, c.current_rss),
                (10, c.zero_ms, c.zero_rss)
        ) AS r(codec_rev, decode_ms, decode_rss)
    )
    SELECT count(*) INTO exact_count
    FROM expected e
    WHERE (SELECT count(*)
           FROM measurements m
           WHERE m.hypothesis_id = 'NEW-30'
             AND m.run_mode = e.run_mode
             AND m.codec_rev = e.codec_rev
             AND m.corpus_file = e.corpus_file
             AND m.orig_bytes = e.orig_bytes
             AND m.comp_bytes = e.comp_bytes
             AND m.ratio = e.comp_bytes::double precision / e.orig_bytes::double precision
             AND m.rt_ok IS TRUE
             AND m.duration_ms IS NULL
             AND m.peak_rss_kib IS NULL
             AND m.decode_ms = e.decode_ms
             AND m.decode_peak_rss_kib = e.decode_rss
             AND m.measured_at = '2026-08-09 11:47:09+00'
             AND m.host = 'dev-ai'
             AND m.cpu_pin = '0-15') = 1;

    IF NOT (
        (total_count = 27 AND total_mode_count = 5
         AND matrix_count = 0 AND matrix_mode_count = 0 AND revision_count = 0
         AND exact_count = 0 AND marker_count = 0)
        OR
        (total_count = 51 AND total_mode_count = 13
         AND matrix_count = 24 AND matrix_mode_count = 8 AND revision_count = 3
         AND exact_count = 24 AND marker_count = 1
         AND right((SELECT measure_note FROM hypotheses WHERE id = 'NEW-30'), length(note_suffix)) = note_suffix)
    ) THEN
        RAISE EXCEPTION 'partial/conflicting NEW-30 matrix state: total rows %, total modes %, matrix rows %, matrix modes %, revisions %, exact rows %, note markers %',
            total_count, total_mode_count, matrix_count, matrix_mode_count, revision_count, exact_count, marker_count;
    END IF;
END
$preflight$;

UPDATE hypotheses
SET measure_note = coalesce(measure_note, '') || E'\n\n[EXTENSION 2026-08-09 · CUBR-ZEROREP-MATRIX-G3] Preregistered eight-cell zero-representation matrix completed under systemd with result=success/exit 0, pin 0-15, threads 4, one warmup and three interleaved decode samples per build. Cell verdicts: nci/balanced=PASS/ACCOUNTING_CONSISTENT; nci/web=PASS/ACCOUNTING_CONSISTENT; dickens/max=PASS/ACCOUNTING_CONSISTENT; dickens/balanced=PASS/ACCOUNTING_CONSISTENT; dickens/web=PASS/ACCOUNTING_CONSISTENT; ooffice/max=PASS/ACCOUNTING_CONSISTENT; ooffice/balanced=PASS/ACCOUNTING_CONSISTENT; ooffice/web=PASS/ACCOUNTING_CONSISTENT. All 24 canonical archives and all 96 round trips passed. Evidence: documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-RESULTS-20260809/. Evaluation remains untouched (0).',
    updated_at = now()
WHERE id = 'NEW-30'
  AND strpos(coalesce(measure_note, ''), '[EXTENSION 2026-08-09 · CUBR-ZEROREP-MATRIX-G3]') = 0
  AND NOT EXISTS (
      SELECT 1
      FROM measurements
      WHERE hypothesis_id = 'NEW-30'
        AND run_mode IN (
            'zerorep-nci-balanced-pin0-15-t4',
            'zerorep-nci-web-pin0-15-t4',
            'zerorep-dickens-max-pin0-15-t4',
            'zerorep-dickens-balanced-pin0-15-t4',
            'zerorep-dickens-web-pin0-15-t4',
            'zerorep-ooffice-max-pin0-15-t4',
            'zerorep-ooffice-balanced-pin0-15-t4',
            'zerorep-ooffice-web-pin0-15-t4'
        )
  );

WITH cells(file_name, preset, comp_bytes, base_ms, base_rss, current_ms, current_rss, zero_ms, zero_rss) AS (
    VALUES
        ('nci', 'balanced', 108014, 18170, 1385472::bigint, 15070, 1645056::bigint, 14680, 991744::bigint),
        ('nci', 'web', 108624, 15770, 108032::bigint, 13390, 111616::bigint, 13080, 92672::bigint),
        ('dickens', 'max', 461437, 26940, 1543680::bigint, 19950, 1719808::bigint, 20060, 1154560::bigint),
        ('dickens', 'balanced', 472253, 25710, 1486848::bigint, 19250, 1654272::bigint, 19330, 1135104::bigint),
        ('dickens', 'web', 487506, 22540, 110080::bigint, 17170, 113152::bigint, 17080, 104960::bigint),
        ('ooffice', 'max', 677605, 25530, 1635328::bigint, 19080, 1708544::bigint, 19210, 1474048::bigint),
        ('ooffice', 'balanced', 677605, 25540, 1635328::bigint, 19070, 1708032::bigint, 19340, 1474048::bigint),
        ('ooffice', 'web', 704087, 22290, 112640::bigint, 17120, 115200::bigint, 16800, 108032::bigint)
),
expected AS (
    SELECT
        'zerorep-' || c.file_name || '-' || c.preset || '-pin0-15-t4' AS run_mode,
        'silesia/' || c.file_name || '[0:2097152]' AS corpus_file,
        2097152::bigint AS orig_bytes,
        c.comp_bytes::bigint AS comp_bytes,
        r.codec_rev,
        r.decode_ms,
        r.decode_rss
    FROM cells c
    CROSS JOIN LATERAL (
        VALUES
            (9, c.base_ms, c.base_rss),
            (8, c.current_ms, c.current_rss),
            (10, c.zero_ms, c.zero_rss)
    ) AS r(codec_rev, decode_ms, decode_rss)
)
INSERT INTO measurements (
    hypothesis_id, codec_rev, corpus_file, run_mode,
    orig_bytes, comp_bytes, ratio, rt_ok,
    duration_ms, measured_at, peak_rss_kib,
    decode_ms, decode_peak_rss_kib, host, cpu_pin
)
SELECT
    'NEW-30', e.codec_rev, e.corpus_file, e.run_mode,
    e.orig_bytes, e.comp_bytes, e.comp_bytes::double precision / e.orig_bytes::double precision, true,
    NULL, '2026-08-09 11:47:09+00', NULL,
    e.decode_ms, e.decode_rss, 'dev-ai', '0-15'
FROM expected e
WHERE NOT EXISTS (
    SELECT 1
    FROM measurements
    WHERE hypothesis_id = 'NEW-30'
      AND run_mode IN (
          'zerorep-nci-balanced-pin0-15-t4',
          'zerorep-nci-web-pin0-15-t4',
          'zerorep-dickens-max-pin0-15-t4',
          'zerorep-dickens-balanced-pin0-15-t4',
          'zerorep-dickens-web-pin0-15-t4',
          'zerorep-ooffice-max-pin0-15-t4',
          'zerorep-ooffice-balanced-pin0-15-t4',
          'zerorep-ooffice-web-pin0-15-t4'
      )
);

DO $assertions$
DECLARE
    total_count integer;
    total_mode_count integer;
    matrix_count integer;
    matrix_mode_count integer;
    revision_count integer;
    exact_count integer;
    marker_count integer;
    frozen_existing jsonb;
    current_existing jsonb;
    note_marker constant text := '[EXTENSION 2026-08-09 · CUBR-ZEROREP-MATRIX-G3]';
    note_suffix constant text := E'\n\n[EXTENSION 2026-08-09 · CUBR-ZEROREP-MATRIX-G3] Preregistered eight-cell zero-representation matrix completed under systemd with result=success/exit 0, pin 0-15, threads 4, one warmup and three interleaved decode samples per build. Cell verdicts: nci/balanced=PASS/ACCOUNTING_CONSISTENT; nci/web=PASS/ACCOUNTING_CONSISTENT; dickens/max=PASS/ACCOUNTING_CONSISTENT; dickens/balanced=PASS/ACCOUNTING_CONSISTENT; dickens/web=PASS/ACCOUNTING_CONSISTENT; ooffice/max=PASS/ACCOUNTING_CONSISTENT; ooffice/balanced=PASS/ACCOUNTING_CONSISTENT; ooffice/web=PASS/ACCOUNTING_CONSISTENT. All 24 canonical archives and all 96 round trips passed. Evidence: documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-RESULTS-20260809/. Evaluation remains untouched (0).';
BEGIN
    SELECT rows INTO STRICT frozen_existing
    FROM frozen_new30_snapshot;

    SELECT jsonb_agg(to_jsonb(m) ORDER BY id)
    INTO current_existing
    FROM measurements m
    WHERE hypothesis_id = 'NEW-30'
      AND run_mode NOT IN (
          'zerorep-nci-balanced-pin0-15-t4',
          'zerorep-nci-web-pin0-15-t4',
          'zerorep-dickens-max-pin0-15-t4',
          'zerorep-dickens-balanced-pin0-15-t4',
          'zerorep-dickens-web-pin0-15-t4',
          'zerorep-ooffice-max-pin0-15-t4',
          'zerorep-ooffice-balanced-pin0-15-t4',
          'zerorep-ooffice-web-pin0-15-t4'
      );

    IF current_existing IS DISTINCT FROM frozen_existing THEN
        RAISE EXCEPTION 'preexisting NEW-30 measurement snapshot changed during transaction';
    END IF;

    SELECT count(*), count(DISTINCT run_mode)
    INTO total_count, total_mode_count
    FROM measurements
    WHERE hypothesis_id = 'NEW-30';

    SELECT count(*), count(DISTINCT run_mode), count(DISTINCT codec_rev)
    INTO matrix_count, matrix_mode_count, revision_count
    FROM measurements
    WHERE hypothesis_id = 'NEW-30'
      AND run_mode IN (
          'zerorep-nci-balanced-pin0-15-t4',
          'zerorep-nci-web-pin0-15-t4',
          'zerorep-dickens-max-pin0-15-t4',
          'zerorep-dickens-balanced-pin0-15-t4',
          'zerorep-dickens-web-pin0-15-t4',
          'zerorep-ooffice-max-pin0-15-t4',
          'zerorep-ooffice-balanced-pin0-15-t4',
          'zerorep-ooffice-web-pin0-15-t4'
      );

    WITH cells(file_name, preset, comp_bytes, base_ms, base_rss, current_ms, current_rss, zero_ms, zero_rss) AS (
        VALUES
            ('nci', 'balanced', 108014, 18170, 1385472::bigint, 15070, 1645056::bigint, 14680, 991744::bigint),
            ('nci', 'web', 108624, 15770, 108032::bigint, 13390, 111616::bigint, 13080, 92672::bigint),
            ('dickens', 'max', 461437, 26940, 1543680::bigint, 19950, 1719808::bigint, 20060, 1154560::bigint),
            ('dickens', 'balanced', 472253, 25710, 1486848::bigint, 19250, 1654272::bigint, 19330, 1135104::bigint),
            ('dickens', 'web', 487506, 22540, 110080::bigint, 17170, 113152::bigint, 17080, 104960::bigint),
            ('ooffice', 'max', 677605, 25530, 1635328::bigint, 19080, 1708544::bigint, 19210, 1474048::bigint),
            ('ooffice', 'balanced', 677605, 25540, 1635328::bigint, 19070, 1708032::bigint, 19340, 1474048::bigint),
            ('ooffice', 'web', 704087, 22290, 112640::bigint, 17120, 115200::bigint, 16800, 108032::bigint)
    ),
    expected AS (
        SELECT
            'zerorep-' || c.file_name || '-' || c.preset || '-pin0-15-t4' AS run_mode,
            'silesia/' || c.file_name || '[0:2097152]' AS corpus_file,
            2097152::bigint AS orig_bytes,
            c.comp_bytes::bigint AS comp_bytes,
            r.codec_rev,
            r.decode_ms,
            r.decode_rss
        FROM cells c
        CROSS JOIN LATERAL (
            VALUES
                (9, c.base_ms, c.base_rss),
                (8, c.current_ms, c.current_rss),
                (10, c.zero_ms, c.zero_rss)
        ) AS r(codec_rev, decode_ms, decode_rss)
    )
    SELECT count(*) INTO exact_count
    FROM expected e
    WHERE (SELECT count(*)
           FROM measurements m
           WHERE m.hypothesis_id = 'NEW-30'
             AND m.run_mode = e.run_mode
             AND m.codec_rev = e.codec_rev
             AND m.corpus_file = e.corpus_file
             AND m.orig_bytes = e.orig_bytes
             AND m.comp_bytes = e.comp_bytes
             AND m.ratio = e.comp_bytes::double precision / e.orig_bytes::double precision
             AND m.rt_ok IS TRUE
             AND m.duration_ms IS NULL
             AND m.peak_rss_kib IS NULL
             AND m.decode_ms = e.decode_ms
             AND m.decode_peak_rss_kib = e.decode_rss
             AND m.measured_at = '2026-08-09 11:47:09+00'
             AND m.host = 'dev-ai'
             AND m.cpu_pin = '0-15') = 1;

    SELECT (length(coalesce(measure_note, '')) - length(replace(coalesce(measure_note, ''), note_marker, ''))) / length(note_marker)
    INTO marker_count
    FROM hypotheses
    WHERE id = 'NEW-30';

    IF total_count <> 51 OR total_mode_count <> 13
       OR matrix_count <> 24 OR matrix_mode_count <> 8 OR revision_count <> 3
       OR exact_count <> 24 THEN
        RAISE EXCEPTION 'post-insert measurement assertions failed: total rows %, total modes %, matrix rows %, matrix modes %, revisions %, exact rows %',
            total_count, total_mode_count, matrix_count, matrix_mode_count, revision_count, exact_count;
    END IF;

    IF (SELECT count(*)
        FROM codec_revisions
        WHERE (id = 9 AND sha = 'cli-sha256:a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd')
           OR (id = 8 AND sha = 'cli-sha256:12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c')
           OR (id = 10 AND sha = 'cli-sha256:771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20')) <> 3 THEN
        RAISE EXCEPTION 'post-insert codec mapping changed';
    END IF;

    IF marker_count <> 1
       OR right((SELECT measure_note FROM hypotheses WHERE id = 'NEW-30'), length(note_suffix)) <> note_suffix THEN
        RAISE EXCEPTION 'NEW-30 matrix note is missing, duplicated, or conflicting: marker count %', marker_count;
    END IF;

    IF (SELECT count(*)
        FROM web_benchmark_hypothesis_evaluation e
        JOIN web_benchmark_hypothesis h ON h.id = e.hypothesis_id
        WHERE h.task_id = 'NEW-30') <> 0 THEN
        RAISE EXCEPTION 'NEW-30 evaluation changed';
    END IF;
END
$assertions$;

SELECT
    'transaction_rows' AS label,
    count(*) AS rows,
    count(DISTINCT run_mode) AS modes,
    count(DISTINCT codec_rev) AS revisions
FROM measurements
WHERE hypothesis_id = 'NEW-30'
  AND run_mode IN (
      'zerorep-nci-balanced-pin0-15-t4',
      'zerorep-nci-web-pin0-15-t4',
      'zerorep-dickens-max-pin0-15-t4',
      'zerorep-dickens-balanced-pin0-15-t4',
      'zerorep-dickens-web-pin0-15-t4',
      'zerorep-ooffice-max-pin0-15-t4',
      'zerorep-ooffice-balanced-pin0-15-t4',
      'zerorep-ooffice-web-pin0-15-t4'
  );

COMMIT;
