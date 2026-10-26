-- Live updates for the admin (toasts, the bell, "updates available" bars): one row per thing staff may want to hear
-- about at once — a new order, a payment, a new message … Written in the same transaction as the change by the
-- after_flush hook in app/core/live_events.py; read as "everything after id N". Kept for 7 days (retention job).
CREATE TABLE live_events (
    id BIGSERIAL PRIMARY KEY,
    kind VARCHAR(40) NOT NULL,           -- order.new, order.paid, order.status, order.refund, customer.new, message.new …
    ref_id BIGINT,                       -- the record it is about (order id, message id …)
    title VARCHAR(200) NOT NULL,
    detail VARCHAR(300),
    href VARCHAR(300),                   -- the admin page that handles it
    permission VARCHAR(40) NOT NULL,     -- who may see it (app/core/permissions.py)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_live_events_created_at ON live_events (created_at);
