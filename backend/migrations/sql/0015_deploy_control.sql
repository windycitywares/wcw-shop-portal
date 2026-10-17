-- Admin → Deployments: when the server looks for updates (automatic, scheduled or paused), a pending "Deploy now",
-- and what the last run did. One row, always read as public.deploy_control (live), whatever Test mode is set to.
CREATE TABLE deploy_control (
    id INTEGER PRIMARY KEY DEFAULT 1,
    mode VARCHAR(10) NOT NULL DEFAULT 'auto',               -- auto | schedule | paused
    interval_minutes INTEGER NOT NULL DEFAULT 10,
    schedule_times JSONB NOT NULL DEFAULT '[]'::jsonb,      -- ["02:00", "16:00"], store time (America/Chicago)
    requested_at TIMESTAMPTZ,                               -- "Deploy now" waiting for the cron job
    requested_by_email VARCHAR(320),
    last_seen_at TIMESTAMPTZ,                               -- the cron job's heartbeat (every run)
    last_check_at TIMESTAMPTZ,                              -- last time it looked for updates
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    last_reason VARCHAR(40),
    last_result TEXT,
    updated_at TIMESTAMPTZ,
    updated_by_email VARCHAR(320),
    CONSTRAINT ck_deploy_control_single CHECK (id = 1),
    CONSTRAINT ck_deploy_control_mode CHECK (mode IN ('auto', 'schedule', 'paused')),
    CONSTRAINT ck_deploy_control_interval CHECK (interval_minutes BETWEEN 1 AND 1440)
);
INSERT INTO deploy_control (id) VALUES (1);
