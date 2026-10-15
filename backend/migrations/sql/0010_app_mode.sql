-- Live / Test switch. One row; read as public.app_mode on every connection (see app/core/appmode.py).
CREATE TABLE app_mode (
    id               SMALLINT PRIMARY KEY DEFAULT 1,
    mode             VARCHAR(8) NOT NULL DEFAULT 'live',
    test_mail_to     VARCHAR(320),
    test_synced_at   TIMESTAMPTZ,
    changed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    changed_by_email VARCHAR(320),
    CONSTRAINT ck_app_mode_single CHECK (id = 1),
    CONSTRAINT ck_app_mode_mode CHECK (mode IN ('live', 'test'))
);

INSERT INTO app_mode (id, mode) VALUES (1, 'live');
