-- Changes the CRM (crm.windycitywares.com) must hear about. A row only says "this order/account/subscriber changed";
-- the sync job builds the current data when it sends, signs it and posts it to the CRM (docs/CRM_SYNC.md).
CREATE TABLE crm_outbox (
    id BIGSERIAL PRIMARY KEY,
    kind VARCHAR(20) NOT NULL,             -- order | customer | newsletter
    ref_id BIGINT NOT NULL,                -- orders.id | users.id | newsletter_subscribers.id
    status VARCHAR(10) NOT NULL DEFAULT 'pending',  -- pending | sent | skipped | merged | failed
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_crm_outbox_due ON crm_outbox (status, next_attempt_at);
CREATE INDEX ix_crm_outbox_ref ON crm_outbox (kind, ref_id);
