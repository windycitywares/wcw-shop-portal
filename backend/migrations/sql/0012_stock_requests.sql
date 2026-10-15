-- Stock requests: "email me when it's back" for a chosen option combination, or a request for a combination the
-- shop doesn't sell (kind = 'request', handled by staff). Signed-in customers only from now on.
ALTER TABLE stock_alerts
    ADD COLUMN options    JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN note       TEXT,
    ADD COLUMN kind       VARCHAR(10) NOT NULL DEFAULT 'restock',
    ADD COLUMN closed_at  TIMESTAMPTZ,
    ADD COLUMN handled_by_email VARCHAR(320);

ALTER TABLE stock_alerts
    ADD CONSTRAINT ck_stock_alerts_kind CHECK (kind IN ('restock', 'request'));

DROP INDEX uq_stock_alerts_waiting;
CREATE UNIQUE INDEX uq_stock_alerts_waiting ON stock_alerts (product_id, lower(email), options)
    WHERE notified_at IS NULL AND closed_at IS NULL;
CREATE INDEX ix_stock_alerts_user ON stock_alerts (user_id, created_at DESC);
