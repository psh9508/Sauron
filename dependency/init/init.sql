CREATE TABLE IF NOT EXISTS scm_connections (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL UNIQUE,
    provider VARCHAR(20) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    repo_name VARCHAR(255) NOT NULL,
    app_id VARCHAR(100) NOT NULL,
    installation_id VARCHAR(100) NOT NULL,
    encrypted_pem TEXT NOT NULL,
    is_active BOOL NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_scm_connections_provider
        CHECK (provider IN ('github', 'gitlab')),
    CONSTRAINT uq_scm_connections_repo
        UNIQUE (provider, owner, repo_name)
);

CREATE INDEX IF NOT EXISTS idx_scm_connections_project_active
    ON scm_connections (project_id, is_active);

CREATE TABLE IF NOT EXISTS analyze_jobs (
    id UUID PRIMARY KEY,
    project_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_message_input TEXT NOT NULL,
    stack_trace TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_analyze_jobs_project_created_at
    ON analyze_jobs (project_id, created_at DESC);
