-- schema.sql — FBDD Bridge v2.0
-- Apply once:
--   createdb fbdd_bridge
--   psql fbdd_bridge < schema.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- provides gen_random_uuid()

CREATE TABLE IF NOT EXISTS jobs (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_job_id         UUID        REFERENCES jobs(id) ON DELETE CASCADE,
    job_type              VARCHAR(50) NOT NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'queued',

    -- discovery context
    target                VARCHAR(50),
    diagnosis             VARCHAR(200),
    generation            INTEGER     DEFAULT 1,
    params                JSONB,
    patient               JSONB,
    reference_drug        VARCHAR(100),
    reference_affinity    DOUBLE PRECISION,

    -- runtime / filesystem
    pid                   INTEGER,
    log_file              VARCHAR(500),
    results_file          VARCHAR(500),

    -- outputs
    best_candidate        JSONB,
    leaderboard           JSONB,
    error_message         TEXT,

    -- timestamps
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at            TIMESTAMPTZ,
    completed_at          TIMESTAMPTZ,

    CONSTRAINT jobs_status_ck CHECK (
        status IN ('queued', 'running', 'done', 'error', 'stopped')
    ),
    CONSTRAINT jobs_type_ck CHECK (job_type IN ('fbdd', 'ppi'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_parent  ON jobs(parent_job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_target  ON jobs(target);

-- Safety: mark any jobs that were 'running' at the time of a bridge crash
-- as 'error' the next time the schema file is applied. Optional; comment
-- out if you don't want this behavior.
UPDATE jobs
   SET status = 'error',
       error_message = COALESCE(error_message, 'Bridge restarted while running'),
       completed_at = NOW()
 WHERE status IN ('queued', 'running');
