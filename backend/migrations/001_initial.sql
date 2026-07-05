-- ============================================================
-- Distributed Job Scheduler — Database Migration 001
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name   VARCHAR(255),
    is_active   BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- 2. ORGANIZATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_orgs_slug ON organizations(slug);

-- ============================================================
-- 3. ORGANIZATION MEMBERS (RBAC)
-- ============================================================
CREATE TABLE IF NOT EXISTS organization_members (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(50) NOT NULL DEFAULT 'member',
    invited_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, user_id),
    CHECK (role IN ('owner','admin','member','viewer'))
);
CREATE INDEX idx_org_members_user ON organization_members(user_id);
CREATE INDEX idx_org_members_org  ON organization_members(org_id);

-- ============================================================
-- 4. PROJECTS
-- ============================================================
CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) NOT NULL,
    description TEXT,
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, slug)
);
CREATE INDEX idx_projects_org ON projects(org_id);

-- ============================================================
-- 5. API KEYS
-- ============================================================
CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    key_hash    VARCHAR(255) NOT NULL,
    key_prefix  VARCHAR(20) NOT NULL,
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    last_used_at TIMESTAMPTZ,
    expires_at  TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_api_keys_project ON api_keys(project_id);
CREATE INDEX idx_api_keys_hash    ON api_keys(key_hash);

-- ============================================================
-- 6. RETRY POLICIES
-- ============================================================
CREATE TABLE IF NOT EXISTS retry_policies (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 VARCHAR(255),
    strategy             VARCHAR(50) NOT NULL DEFAULT 'exponential',
    max_attempts         INTEGER NOT NULL DEFAULT 3,
    initial_delay_seconds INTEGER NOT NULL DEFAULT 60,
    max_delay_seconds    INTEGER DEFAULT 3600,
    multiplier           FLOAT DEFAULT 2.0,
    jitter               BOOLEAN DEFAULT FALSE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (strategy IN ('fixed','linear','exponential'))
);

-- Insert sensible defaults
INSERT INTO retry_policies (name, strategy, max_attempts, initial_delay_seconds, max_delay_seconds, multiplier, jitter)
VALUES
    ('No Retry',          'fixed',        1,  0,    0,    1.0, FALSE),
    ('Fixed 60s',         'fixed',        3,  60,   60,   1.0, FALSE),
    ('Linear Backoff',    'linear',       5,  30,   300,  1.0, TRUE),
    ('Exponential 2x',    'exponential',  5,  30,   3600, 2.0, TRUE)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 7. QUEUES
-- ============================================================
CREATE TABLE IF NOT EXISTS queues (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name                 VARCHAR(255) NOT NULL,
    slug                 VARCHAR(100) NOT NULL,
    description          TEXT,
    priority             INTEGER NOT NULL DEFAULT 5,
    concurrency_limit    INTEGER NOT NULL DEFAULT 10,
    rate_limit_per_minute INTEGER,
    retry_policy_id      UUID REFERENCES retry_policies(id) ON DELETE SET NULL,
    is_paused            BOOLEAN DEFAULT FALSE,
    is_active            BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, slug),
    CHECK (priority BETWEEN 1 AND 10),
    CHECK (concurrency_limit > 0)
);
CREATE INDEX idx_queues_project ON queues(project_id);

-- ============================================================
-- 8. WORKERS
-- ============================================================
CREATE TABLE IF NOT EXISTS workers (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             VARCHAR(255),
    hostname         VARCHAR(255),
    ip_address       VARCHAR(45),
    pid              INTEGER,
    status           VARCHAR(50) NOT NULL DEFAULT 'active',
    capabilities     TEXT[] DEFAULT '{}',
    max_concurrency  INTEGER NOT NULL DEFAULT 10,
    current_jobs     INTEGER NOT NULL DEFAULT 0,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shutdown_at      TIMESTAMPTZ,
    CHECK (status IN ('active','idle','draining','offline'))
);
CREATE INDEX idx_workers_status ON workers(status);
CREATE INDEX idx_workers_heartbeat ON workers(last_heartbeat_at);

-- ============================================================
-- 9. BATCH JOBS
-- ============================================================
CREATE TABLE IF NOT EXISTS batch_jobs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id       UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    name           VARCHAR(255),
    total_jobs     INTEGER NOT NULL DEFAULT 0,
    completed_jobs INTEGER NOT NULL DEFAULT 0,
    failed_jobs    INTEGER NOT NULL DEFAULT 0,
    status         VARCHAR(50) NOT NULL DEFAULT 'running',
    created_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMPTZ,
    CHECK (status IN ('running','completed','partial','failed'))
);

-- ============================================================
-- 10. JOBS
-- ============================================================
CREATE TABLE IF NOT EXISTS jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id         UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    batch_id         UUID REFERENCES batch_jobs(id) ON DELETE SET NULL,
    name             VARCHAR(255),
    job_type         VARCHAR(50) NOT NULL DEFAULT 'immediate',
    handler          VARCHAR(255) NOT NULL DEFAULT 'default',
    payload          JSONB NOT NULL DEFAULT '{}',
    status           VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority         INTEGER NOT NULL DEFAULT 5,
    max_attempts     INTEGER NOT NULL DEFAULT 3,
    attempt_count    INTEGER NOT NULL DEFAULT 0,
    timeout_seconds  INTEGER NOT NULL DEFAULT 300,
    scheduled_at     TIMESTAMPTZ,
    cron_expression  VARCHAR(255),
    next_run_at      TIMESTAMPTZ,
    claimed_at       TIMESTAMPTZ,
    claimed_by       UUID REFERENCES workers(id) ON DELETE SET NULL,
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    result           JSONB,
    error_message    TEXT,
    idempotency_key  VARCHAR(255),
    tags             TEXT[] DEFAULT '{}',
    metadata         JSONB DEFAULT '{}',
    created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at       TIMESTAMPTZ,
    CHECK (job_type IN ('immediate','delayed','scheduled','recurring','batch')),
    CHECK (status IN ('pending','scheduled','claimed','running','completed','failed','cancelled','dead_letter')),
    CHECK (priority BETWEEN 1 AND 10)
);
-- Core polling index: queue + status + priority ordering
CREATE INDEX idx_jobs_poll ON jobs(queue_id, status, priority DESC, scheduled_at ASC NULLS FIRST)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_jobs_status ON jobs(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_jobs_scheduled ON jobs(scheduled_at)
    WHERE status IN ('pending','scheduled') AND deleted_at IS NULL;
CREATE INDEX idx_jobs_cron ON jobs(next_run_at)
    WHERE job_type = 'recurring' AND deleted_at IS NULL;
CREATE UNIQUE INDEX idx_jobs_idempotency ON jobs(queue_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL;

-- ============================================================
-- 11. JOB DEPENDENCIES (DAG Workflow)
-- ============================================================
CREATE TABLE IF NOT EXISTS job_dependencies (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id            UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    depends_on_job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(job_id, depends_on_job_id),
    CHECK (job_id != depends_on_job_id)
);
CREATE INDEX idx_job_deps_job ON job_dependencies(job_id);
CREATE INDEX idx_job_deps_depends_on ON job_dependencies(depends_on_job_id);

-- ============================================================
-- 12. JOB EXECUTIONS (partitioned by month)
-- ============================================================
CREATE TABLE IF NOT EXISTS job_executions (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    job_id         UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    worker_id      UUID REFERENCES workers(id) ON DELETE SET NULL,
    attempt_number INTEGER NOT NULL,
    status         VARCHAR(50) NOT NULL,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMPTZ,
    duration_ms    INTEGER,
    exit_code      INTEGER,
    error_type     VARCHAR(255),
    error_message  TEXT,
    error_stack    TEXT,
    result         JSONB,
    memory_mb      FLOAT,
    cpu_time_ms    INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('running','completed','failed','timed_out','cancelled'))
) PARTITION BY RANGE (created_at);

CREATE TABLE job_executions_2025 PARTITION OF job_executions
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE job_executions_2026 PARTITION OF job_executions
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
CREATE TABLE job_executions_2027 PARTITION OF job_executions
    FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');
CREATE TABLE job_executions_default PARTITION OF job_executions DEFAULT;

CREATE INDEX idx_job_executions_job   ON job_executions(job_id);
CREATE INDEX idx_job_executions_worker ON job_executions(worker_id);

-- ============================================================
-- 13. JOB LOGS (partitioned by month)
-- ============================================================
CREATE TABLE IF NOT EXISTS job_logs (
    id           BIGSERIAL,
    execution_id UUID NOT NULL,
    job_id       UUID NOT NULL,
    level        VARCHAR(20) NOT NULL DEFAULT 'info',
    message      TEXT NOT NULL,
    data         JSONB,
    logged_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (level IN ('debug','info','warn','error'))
) PARTITION BY RANGE (logged_at);

CREATE TABLE job_logs_2025 PARTITION OF job_logs
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE job_logs_2026 PARTITION OF job_logs
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
CREATE TABLE job_logs_2027 PARTITION OF job_logs
    FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');
CREATE TABLE job_logs_default PARTITION OF job_logs DEFAULT;

CREATE INDEX idx_job_logs_execution ON job_logs(execution_id);
CREATE INDEX idx_job_logs_job       ON job_logs(job_id);

-- ============================================================
-- 14. DEAD LETTER QUEUE
-- ============================================================
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id            UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    queue_id          UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    final_error       TEXT,
    total_attempts    INTEGER NOT NULL DEFAULT 0,
    moved_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at       TIMESTAMPTZ,
    resolution        VARCHAR(50),
    ai_failure_summary TEXT,
    CHECK (resolution IN ('retried','discarded') OR resolution IS NULL)
);
CREATE INDEX idx_dlq_queue ON dead_letter_queue(queue_id, moved_at DESC);
CREATE INDEX idx_dlq_job   ON dead_letter_queue(job_id);

-- ============================================================
-- 15. WORKER HEARTBEATS
-- ============================================================
CREATE TABLE IF NOT EXISTS worker_heartbeats (
    id           BIGSERIAL PRIMARY KEY,
    worker_id    UUID NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    status       VARCHAR(50),
    current_jobs INTEGER,
    memory_mb    FLOAT,
    cpu_percent  FLOAT,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_heartbeats_worker ON worker_heartbeats(worker_id, recorded_at DESC);

-- ============================================================
-- 16. QUEUE STATS SNAPSHOTS
-- ============================================================
CREATE TABLE IF NOT EXISTS queue_stats_snapshots (
    id                    BIGSERIAL PRIMARY KEY,
    queue_id              UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    pending_count         INTEGER NOT NULL DEFAULT 0,
    running_count         INTEGER NOT NULL DEFAULT 0,
    completed_count       INTEGER NOT NULL DEFAULT 0,
    failed_count          INTEGER NOT NULL DEFAULT 0,
    dead_letter_count     INTEGER NOT NULL DEFAULT 0,
    avg_wait_time_ms      FLOAT,
    avg_execution_time_ms FLOAT,
    throughput_per_minute FLOAT,
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_queue_stats ON queue_stats_snapshots(queue_id, recorded_at DESC);

-- ============================================================
-- 17. EVENTS / AUDIT LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(100) NOT NULL,
    entity_id   UUID NOT NULL,
    event_type  VARCHAR(100) NOT NULL,
    actor_id    UUID,
    actor_type  VARCHAR(50),
    data        JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_events_entity ON events(entity_type, entity_id, created_at DESC);
CREATE INDEX idx_events_type   ON events(event_type, created_at DESC);

-- ============================================================
-- 18. RATE LIMIT BUCKETS (Token Bucket)
-- ============================================================
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    queue_id      UUID PRIMARY KEY REFERENCES queues(id) ON DELETE CASCADE,
    tokens        FLOAT NOT NULL,
    max_tokens    FLOAT NOT NULL,
    refill_rate   FLOAT NOT NULL,
    last_refill_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 19. DISTRIBUTED LOCKS
-- ============================================================
CREATE TABLE IF NOT EXISTS distributed_locks (
    lock_key   VARCHAR(255) PRIMARY KEY,
    owner      VARCHAR(255) NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_locks_expires ON distributed_locks(expires_at);

-- ============================================================
-- 20. SCHEDULED JOBS (cron job definitions separate from instances)
-- ============================================================
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id        UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    handler         VARCHAR(255) NOT NULL DEFAULT 'default',
    payload         JSONB NOT NULL DEFAULT '{}',
    cron_expression VARCHAR(255) NOT NULL,
    timezone        VARCHAR(100) NOT NULL DEFAULT 'UTC',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_scheduled_next_run ON scheduled_jobs(next_run_at) WHERE is_active = TRUE;

-- ============================================================
-- Helper function: auto-update updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_orgs_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_queues_updated_at
    BEFORE UPDATE ON queues
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_scheduled_jobs_updated_at
    BEFORE UPDATE ON scheduled_jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
