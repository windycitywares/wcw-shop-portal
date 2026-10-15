-- Reverses 0012_stock_requests.sql
DROP INDEX ix_stock_alerts_user;
DROP INDEX uq_stock_alerts_waiting;
DELETE FROM stock_alerts a USING stock_alerts b
    WHERE a.id > b.id AND a.product_id = b.product_id AND a.email = b.email AND a.notified_at IS NULL AND b.notified_at IS NULL;
CREATE UNIQUE INDEX uq_stock_alerts_waiting ON stock_alerts (product_id, email) WHERE notified_at IS NULL;
ALTER TABLE stock_alerts DROP CONSTRAINT ck_stock_alerts_kind;
ALTER TABLE stock_alerts DROP COLUMN handled_by_email, DROP COLUMN closed_at, DROP COLUMN kind, DROP COLUMN note, DROP COLUMN options;
