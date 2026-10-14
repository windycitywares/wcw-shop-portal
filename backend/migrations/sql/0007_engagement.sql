-- Engagement: reviews, wishlists, back-in-stock alerts, newsletter consent registry, email campaigns.
-- Mirrors app/models/engagement.py. Keep semicolons out of comments and string literals.

ALTER TABLE products ADD COLUMN rating_avg NUMERIC(3, 2) NOT NULL DEFAULT 0;
ALTER TABLE products ADD COLUMN rating_count INTEGER NOT NULL DEFAULT 0;

-- The newsletter table doubles as the marketing consent registry (opt-ins and unsubscribes).
ALTER TABLE newsletter_subscribers ADD COLUMN locale VARCHAR(5);
ALTER TABLE newsletter_subscribers ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'site';
ALTER TABLE newsletter_subscribers ADD COLUMN unsubscribe_token VARCHAR(40);
ALTER TABLE newsletter_subscribers ADD COLUMN unsubscribed_at TIMESTAMPTZ;
ALTER TABLE newsletter_subscribers ADD COLUMN welcome_coupon VARCHAR(40);
UPDATE newsletter_subscribers SET unsubscribe_token = md5(random()::text || id::text) WHERE unsubscribe_token IS NULL;
ALTER TABLE newsletter_subscribers ALTER COLUMN unsubscribe_token SET NOT NULL;
-- Rows created by code that doesn't set a token still get an unguessable one.
ALTER TABLE newsletter_subscribers ALTER COLUMN unsubscribe_token SET DEFAULT md5(random()::text || clock_timestamp()::text);
CREATE UNIQUE INDEX uq_newsletter_subscribers_token ON newsletter_subscribers (unsubscribe_token);

CREATE TABLE reviews (
    id            BIGSERIAL PRIMARY KEY,
    product_id    BIGINT NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    user_id       BIGINT REFERENCES users (id) ON DELETE SET NULL,
    order_id      BIGINT REFERENCES orders (id) ON DELETE SET NULL,
    author_name   VARCHAR(120) NOT NULL,
    rating        SMALLINT NOT NULL,
    title         VARCHAR(160),
    body          TEXT NOT NULL,
    locale        VARCHAR(5),
    status        VARCHAR(10) NOT NULL DEFAULT 'pending',
    verified      BOOLEAN NOT NULL DEFAULT false,
    helpful_count INTEGER NOT NULL DEFAULT 0,
    reply         TEXT,
    replied_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_reviews_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT ck_reviews_status CHECK (status IN ('pending', 'approved', 'rejected'))
);
CREATE INDEX ix_reviews_product ON reviews (product_id, status, created_at DESC);
CREATE INDEX ix_reviews_status ON reviews (status, created_at DESC);
CREATE UNIQUE INDEX uq_reviews_one_per_user ON reviews (product_id, user_id) WHERE user_id IS NOT NULL;

CREATE TABLE review_votes (
    review_id  BIGINT NOT NULL REFERENCES reviews (id) ON DELETE CASCADE,
    user_id    BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (review_id, user_id)
);

CREATE TABLE wishlist_items (
    user_id    BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, product_id)
);
CREATE INDEX ix_wishlist_items_product ON wishlist_items (product_id);

CREATE TABLE stock_alerts (
    id          BIGSERIAL PRIMARY KEY,
    product_id  BIGINT NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    email       VARCHAR(320) NOT NULL,
    user_id     BIGINT REFERENCES users (id) ON DELETE SET NULL,
    locale      VARCHAR(5),
    notified_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_stock_alerts_waiting ON stock_alerts (product_id, email) WHERE notified_at IS NULL;
CREATE INDEX ix_stock_alerts_product ON stock_alerts (product_id);

CREATE TABLE campaigns (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(120) NOT NULL,
    subject             VARCHAR(200) NOT NULL,
    body                TEXT NOT NULL,
    translations        JSONB NOT NULL DEFAULT '{}'::jsonb,
    segment             VARCHAR(20) NOT NULL DEFAULT 'subscribers',
    coupon_kind         VARCHAR(14),
    coupon_value        NUMERIC(12, 2),
    coupon_expires_days INTEGER,
    coupon_min_subtotal NUMERIC(12, 2),
    status              VARCHAR(10) NOT NULL DEFAULT 'draft',
    recipients          INTEGER NOT NULL DEFAULT 0,
    sent_at             TIMESTAMPTZ,
    created_by_id       BIGINT REFERENCES users (id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_campaigns_segment CHECK (segment IN ('subscribers', 'prospects', 'customers', 'new', 'active', 'loyal', 'vip', 'needs_nudge', 'at_risk', 'lapsed')),
    CONSTRAINT ck_campaigns_status CHECK (status IN ('draft', 'sent'))
);
