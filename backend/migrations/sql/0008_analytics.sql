-- First-party, consent-based analytics: sessions, events and a daily consent counter.
-- No IP addresses are stored. Mirrors app/models/analytics.py.

CREATE TABLE analytics_sessions (
    id             VARCHAR(40) PRIMARY KEY,
    visitor_id     VARCHAR(40) NOT NULL,
    user_id        BIGINT REFERENCES users (id) ON DELETE SET NULL,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    landing_path   VARCHAR(500),
    referrer_host  VARCHAR(255),
    channel        VARCHAR(30) NOT NULL DEFAULT 'direct',
    utm_source     VARCHAR(100),
    utm_medium     VARCHAR(100),
    utm_campaign   VARCHAR(150),
    device         VARCHAR(10),
    browser        VARCHAR(30),
    os             VARCHAR(30),
    locale         VARCHAR(5),
    is_new_visitor BOOLEAN NOT NULL DEFAULT true,
    page_views     INTEGER NOT NULL DEFAULT 0,
    event_count    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_analytics_sessions_started ON analytics_sessions (started_at);
CREATE INDEX ix_analytics_sessions_visitor ON analytics_sessions (visitor_id);
CREATE INDEX ix_analytics_sessions_user ON analytics_sessions (user_id) WHERE user_id IS NOT NULL;

CREATE TABLE analytics_events (
    id         BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(40) NOT NULL REFERENCES analytics_sessions (id) ON DELETE CASCADE,
    type       VARCHAR(24) NOT NULL,
    path       VARCHAR(500),
    product_id BIGINT REFERENCES products (id) ON DELETE SET NULL,
    value      NUMERIC(12, 2),
    data       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_analytics_events_created ON analytics_events (created_at);
CREATE INDEX ix_analytics_events_type ON analytics_events (type, created_at);
CREATE INDEX ix_analytics_events_session ON analytics_events (session_id, created_at);
CREATE INDEX ix_analytics_events_product ON analytics_events (product_id, type, created_at) WHERE product_id IS NOT NULL;

CREATE TABLE consent_daily (
    day      DATE PRIMARY KEY,
    accepted INTEGER NOT NULL DEFAULT 0,
    declined INTEGER NOT NULL DEFAULT 0
);
