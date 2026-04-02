CREATE TABLE scm_connections (
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

CREATE INDEX idx_scm_connections_project_active
    ON scm_connections (project_id, is_active);
