-- Automatic database backups to a private GitHub repository (see app/services/backups.py).
CREATE TABLE backup_config (
    id               SMALLINT PRIMARY KEY DEFAULT 1,
    enabled          BOOLEAN NOT NULL DEFAULT false,
    hour             SMALLINT NOT NULL DEFAULT 3,
    keep             SMALLINT NOT NULL DEFAULT 5,
    repo             VARCHAR(200),
    branch           VARCHAR(100) NOT NULL DEFAULT 'main',
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by_email VARCHAR(320),
    CONSTRAINT ck_backup_config_single CHECK (id = 1),
    CONSTRAINT ck_backup_config_hour CHECK (hour BETWEEN 0 AND 23),
    CONSTRAINT ck_backup_config_keep CHECK (keep BETWEEN 1 AND 30)
);
INSERT INTO backup_config (id) VALUES (1);

CREATE TABLE backup_runs (
    id          BIGSERIAL PRIMARY KEY,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status      VARCHAR(10) NOT NULL DEFAULT 'running',
    trigger     VARCHAR(10) NOT NULL,
    actor_email VARCHAR(320),
    file_name   VARCHAR(200),
    size_bytes  BIGINT,
    error       TEXT,
    CONSTRAINT ck_backup_runs_status CHECK (status IN ('running', 'success', 'failed')),
    CONSTRAINT ck_backup_runs_trigger CHECK (trigger IN ('schedule', 'manual'))
);
CREATE INDEX ix_backup_runs_started ON backup_runs (started_at DESC);
