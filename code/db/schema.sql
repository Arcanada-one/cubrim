-- CUBR-0039 — Cubrim hypotheses + measurements canonical store
-- Source of truth for MEASUREMENTS (markdown stays source of truth for DESCRIPTIONS).

CREATE TABLE IF NOT EXISTS hypotheses (
    id           text PRIMARY KEY,              -- 'H-20', 'IW-02', 'H-25k', ...
    title        text NOT NULL,
    meaning      text,
    verdict      text,                          -- WIN/GO/LIVE/SHIPPED/NO-GO/CLOSED/MEASURED/OPEN/...
    status       text,                          -- coarse status shown on site
    runnable     boolean NOT NULL DEFAULT false,-- maps to a real codec --value-scheme?
    value_scheme text,                          -- codec flag if runnable, else NULL
    src          text,                          -- canonical source ref
    md_path      text,                          -- path to the human-authored .md
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS codec_revisions (
    id          serial PRIMARY KEY,
    sha         text NOT NULL,                  -- git sha of the codec (or 'stand-<mtime>' if non-git)
    label       text,                           -- human label
    built_at    timestamptz,
    host        text,                           -- where the binary was built/run
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sha)
);

CREATE TABLE IF NOT EXISTS measurements (
    id            bigserial PRIMARY KEY,
    hypothesis_id text NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    codec_rev     integer NOT NULL REFERENCES codec_revisions(id) ON DELETE CASCADE,
    corpus_file   text NOT NULL,                -- 'dickens', 'silesia/webster', 'enwik8', ...
    run_mode      text NOT NULL,                -- 'auto' (competitive-min) or the explicit --value-scheme
    orig_bytes    bigint NOT NULL,
    comp_bytes    bigint NOT NULL,
    ratio         double precision NOT NULL,    -- comp_bytes / orig_bytes  (lower = better)
    rt_ok         boolean NOT NULL,             -- byte-exact round-trip verified
    duration_ms   integer,
    measured_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (hypothesis_id, codec_rev, corpus_file, run_mode)
);

CREATE INDEX IF NOT EXISTS idx_meas_hyp ON measurements(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_meas_rev ON measurements(codec_rev);

-- Size-weighted overall per (hypothesis, codec_rev): sum(comp)/sum(orig) over RT-ok rows.
CREATE OR REPLACE VIEW hypothesis_overall AS
SELECT hypothesis_id,
       codec_rev,
       run_mode,
       sum(comp_bytes)::double precision / NULLIF(sum(orig_bytes),0) AS overall_ratio,
       count(*)                                                      AS n_files,
       bool_and(rt_ok)                                              AS all_rt_ok,
       max(measured_at)                                            AS last_measured_at
FROM measurements
WHERE rt_ok
GROUP BY hypothesis_id, codec_rev, run_mode;
