CREATE TABLE IF NOT EXISTS code_repositories (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(20) NOT NULL,
    repo_info JSONB NOT NULL,
    is_active BOOL NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_code_repositories_provider
        CHECK (provider IN ('github', 'gitlab'))
);

CREATE INDEX IF NOT EXISTS idx_code_repositories_active
    ON code_repositories (id, is_active);

CREATE TABLE IF NOT EXISTS analyze_jobs (
    id UUID PRIMARY KEY,
    repository_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    request JSONB NOT NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    claimed_at TIMESTAMP NULL,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,
    error_message TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_analyze_jobs_status
        CHECK (status IN ('queued', 'running', 'completed', 'failed'))
);

CREATE TABLE IF NOT EXISTS analyze_job_results (
    job_id UUID PRIMARY KEY,
    result_content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_analyze_job_results_job_id
        FOREIGN KEY (job_id)
        REFERENCES analyze_jobs (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analyze_jobs_status_created_at
    ON analyze_jobs (status, created_at);

CREATE INDEX IF NOT EXISTS idx_analyze_jobs_repository_created_at
    ON analyze_jobs (repository_id, created_at DESC);

CREATE TABLE IF NOT EXISTS error_events (
    id BIGSERIAL PRIMARY KEY,
    fingerprint VARCHAR(32) NOT NULL,
    repository_id BIGINT NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    event_count INT NOT NULL DEFAULT 1,
    analyze_job_id UUID NULL,
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_error_events_fingerprint_repo
        UNIQUE (fingerprint, repository_id)
);

CREATE INDEX IF NOT EXISTS idx_error_events_fingerprint
    ON error_events (fingerprint);
