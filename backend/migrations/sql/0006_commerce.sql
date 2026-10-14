-- Commerce: checkout, orders, payments, sales, coupons, cart rules, server carts, email outbox, audit log.
-- Mirrors app/models/commerce.py and the new columns on products / orders / order_items.
-- Plain PostgreSQL 13 DDL. The Alembic wrapper splits the file on statement-ending semicolons, so keep
-- them out of comments and string literals (tests/test_sqlfile.py checks this).

-- ---------------------------------------------------------------------------------------------
-- Products: purchase cost (for margin) and a running count of units sold (for "best seller")
-- ---------------------------------------------------------------------------------------------
ALTER TABLE products ADD COLUMN cost_price NUMERIC(12, 2);
ALTER TABLE products ADD COLUMN units_sold INTEGER NOT NULL DEFAULT 0;
ALTER TABLE products ADD CONSTRAINT ck_products_cost_nonneg CHECK (cost_price IS NULL OR cost_price >= 0);
CREATE INDEX ix_products_units_sold ON products (units_sold DESC);

-- ---------------------------------------------------------------------------------------------
-- Orders
-- ---------------------------------------------------------------------------------------------
CREATE SEQUENCE order_number_seq START WITH 1001;

ALTER TABLE orders ADD COLUMN access_token VARCHAR(64);
ALTER TABLE orders ADD COLUMN customer_name VARCHAR(200);
ALTER TABLE orders ADD COLUMN phone VARCHAR(40);
ALTER TABLE orders ADD COLUMN locale VARCHAR(5);
ALTER TABLE orders ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid';
ALTER TABLE orders ADD COLUMN refunded_total NUMERIC(12, 2) NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN coupon_code VARCHAR(40);
ALTER TABLE orders ADD COLUMN discounts JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE orders ADD COLUMN tax_rate NUMERIC(6, 3) NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN carrier VARCHAR(60);
ALTER TABLE orders ADD COLUMN tracking_url VARCHAR(500);
ALTER TABLE orders ADD COLUMN session_id VARCHAR(40);
ALTER TABLE orders ADD COLUMN channel VARCHAR(30);
ALTER TABLE orders ADD COLUMN device VARCHAR(10);
ALTER TABLE orders ADD COLUMN idempotency_key VARCHAR(64);
ALTER TABLE orders ADD COLUMN marketing_opt_in BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE orders ADD COLUMN paid_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN shipped_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN delivered_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN cancelled_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN review_requested_at TIMESTAMPTZ;

UPDATE orders SET access_token = md5(random()::text || id::text) || md5(id::text || random()::text) WHERE access_token IS NULL;
ALTER TABLE orders ALTER COLUMN access_token SET NOT NULL;

CREATE UNIQUE INDEX uq_orders_access_token ON orders (access_token);
CREATE UNIQUE INDEX uq_orders_idempotency_key ON orders (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX ix_orders_placed_at ON orders (placed_at);
CREATE INDEX ix_orders_status ON orders (status);
CREATE INDEX ix_orders_paid_at ON orders (paid_at) WHERE paid_at IS NOT NULL;
CREATE INDEX ix_orders_email ON orders (email);
CREATE INDEX ix_orders_session_id ON orders (session_id) WHERE session_id IS NOT NULL;
CREATE INDEX ix_orders_coupon_code ON orders (coupon_code) WHERE coupon_code IS NOT NULL;

ALTER TABLE order_items ADD COLUMN slug VARCHAR(255);
ALTER TABLE order_items ADD COLUMN image_url VARCHAR(1000);
ALTER TABLE order_items ADD COLUMN list_price NUMERIC(12, 2);
ALTER TABLE order_items ADD COLUMN unit_cost NUMERIC(12, 2);
ALTER TABLE order_items ADD COLUMN sale_id BIGINT;
ALTER TABLE order_items ADD COLUMN discount_total NUMERIC(12, 2) NOT NULL DEFAULT 0;
ALTER TABLE order_items ADD COLUMN refunded_quantity INTEGER NOT NULL DEFAULT 0;
CREATE INDEX ix_order_items_product_id ON order_items (product_id);

-- ---------------------------------------------------------------------------------------------
-- Settings (one JSON document per group: shipping, tax, welcome offer ...)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE store_settings (
    key           VARCHAR(60) PRIMARY KEY,
    value         JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by_id BIGINT REFERENCES users (id) ON DELETE SET NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------------------------
-- Sales (time-boxed price reductions shown on product cards)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE sales (
    id                 BIGSERIAL PRIMARY KEY,
    name               VARCHAR(120) NOT NULL,
    badge              VARCHAR(40),
    description        TEXT,
    kind               VARCHAR(10) NOT NULL DEFAULT 'percent',
    value              NUMERIC(12, 2) NOT NULL,
    scope              VARCHAR(10) NOT NULL DEFAULT 'all',
    category_ids       BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    product_ids        BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    exclude_product_ids BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    starts_at          TIMESTAMPTZ,
    ends_at            TIMESTAMPTZ,
    is_active          BOOLEAN NOT NULL DEFAULT true,
    translations       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_id      BIGINT REFERENCES users (id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_sales_kind CHECK (kind IN ('percent', 'fixed')),
    CONSTRAINT ck_sales_scope CHECK (scope IN ('all', 'category', 'products')),
    CONSTRAINT ck_sales_value_positive CHECK (value > 0),
    CONSTRAINT ck_sales_percent_max CHECK (kind <> 'percent' OR value < 100),
    CONSTRAINT ck_sales_window CHECK (starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at)
);
CREATE INDEX ix_sales_active ON sales (is_active, starts_at, ends_at);

-- ---------------------------------------------------------------------------------------------
-- Coupons and their redemptions
-- ---------------------------------------------------------------------------------------------
CREATE TABLE coupons (
    id                 BIGSERIAL PRIMARY KEY,
    code               VARCHAR(40) NOT NULL,
    name               VARCHAR(120),
    kind               VARCHAR(14) NOT NULL DEFAULT 'percent',
    value              NUMERIC(12, 2) NOT NULL DEFAULT 0,
    max_discount       NUMERIC(12, 2),
    min_subtotal       NUMERIC(12, 2) NOT NULL DEFAULT 0,
    scope              VARCHAR(10) NOT NULL DEFAULT 'order',
    category_ids       BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    product_ids        BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    exclude_sale_items BOOLEAN NOT NULL DEFAULT false,
    starts_at          TIMESTAMPTZ,
    expires_at         TIMESTAMPTZ,
    usage_limit        INTEGER,
    per_customer_limit INTEGER,
    first_order_only   BOOLEAN NOT NULL DEFAULT false,
    assigned_email     VARCHAR(320),
    campaign           VARCHAR(80),
    source             VARCHAR(16) NOT NULL DEFAULT 'manual',
    stackable          BOOLEAN NOT NULL DEFAULT false,
    is_active          BOOLEAN NOT NULL DEFAULT true,
    used_count         INTEGER NOT NULL DEFAULT 0,
    created_by_id      BIGINT REFERENCES users (id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_coupons_code UNIQUE (code),
    CONSTRAINT ck_coupons_kind CHECK (kind IN ('percent', 'fixed', 'free_shipping')),
    CONSTRAINT ck_coupons_scope CHECK (scope IN ('order', 'category', 'products')),
    CONSTRAINT ck_coupons_value_nonneg CHECK (value >= 0),
    CONSTRAINT ck_coupons_percent_max CHECK (kind <> 'percent' OR value <= 100),
    CONSTRAINT ck_coupons_limits CHECK (
        (usage_limit IS NULL OR usage_limit > 0) AND (per_customer_limit IS NULL OR per_customer_limit > 0)
    )
);
CREATE INDEX ix_coupons_campaign ON coupons (campaign) WHERE campaign IS NOT NULL;
CREATE INDEX ix_coupons_assigned_email ON coupons (assigned_email) WHERE assigned_email IS NOT NULL;
CREATE INDEX ix_coupons_source ON coupons (source);

CREATE TABLE coupon_redemptions (
    id         BIGSERIAL PRIMARY KEY,
    coupon_id  BIGINT NOT NULL REFERENCES coupons (id) ON DELETE CASCADE,
    order_id   BIGINT NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    user_id    BIGINT REFERENCES users (id) ON DELETE SET NULL,
    email      VARCHAR(320) NOT NULL,
    amount     NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_coupon_redemptions_order UNIQUE (coupon_id, order_id)
);
CREATE INDEX ix_coupon_redemptions_email ON coupon_redemptions (coupon_id, email);

-- ---------------------------------------------------------------------------------------------
-- Automatic cart rules ("spend $100, save 10%", "buy 3, save 15%", weekend free shipping)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE cart_rules (
    id               BIGSERIAL PRIMARY KEY,
    name             VARCHAR(120) NOT NULL,
    kind             VARCHAR(20) NOT NULL,
    threshold_amount NUMERIC(12, 2),
    threshold_qty    INTEGER,
    value            NUMERIC(12, 2) NOT NULL DEFAULT 0,
    max_discount     NUMERIC(12, 2),
    scope            VARCHAR(10) NOT NULL DEFAULT 'order',
    category_ids     BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    product_ids      BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    exclude_sale_items BOOLEAN NOT NULL DEFAULT false,
    starts_at        TIMESTAMPTZ,
    ends_at          TIMESTAMPTZ,
    is_active        BOOLEAN NOT NULL DEFAULT true,
    priority         INTEGER NOT NULL DEFAULT 0,
    translations     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_id    BIGINT REFERENCES users (id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_cart_rules_kind CHECK (kind IN ('spend_percent', 'spend_fixed', 'qty_percent', 'qty_fixed', 'free_shipping')),
    CONSTRAINT ck_cart_rules_scope CHECK (scope IN ('order', 'category', 'products')),
    CONSTRAINT ck_cart_rules_value_nonneg CHECK (value >= 0)
);
CREATE INDEX ix_cart_rules_active ON cart_rules (is_active, starts_at, ends_at);

-- ---------------------------------------------------------------------------------------------
-- Server-side cart snapshots (power abandoned-cart reminders and cart reports)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE carts (
    id                  BIGSERIAL PRIMARY KEY,
    token               VARCHAR(40) NOT NULL,
    user_id             BIGINT REFERENCES users (id) ON DELETE SET NULL,
    email               VARCHAR(320),
    locale              VARCHAR(5),
    items               JSONB NOT NULL DEFAULT '[]'::jsonb,
    item_count          INTEGER NOT NULL DEFAULT 0,
    subtotal            NUMERIC(12, 2) NOT NULL DEFAULT 0,
    coupon_code         VARCHAR(40),
    session_id          VARCHAR(40),
    reminders_ok        BOOLEAN NOT NULL DEFAULT false,
    last_activity_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    checkout_started_at TIMESTAMPTZ,
    converted_order_id  BIGINT REFERENCES orders (id) ON DELETE SET NULL,
    converted_at        TIMESTAMPTZ,
    reminder_count      INTEGER NOT NULL DEFAULT 0,
    last_reminder_at    TIMESTAMPTZ,
    recovery_coupon     VARCHAR(40),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_carts_token UNIQUE (token)
);
CREATE INDEX ix_carts_last_activity ON carts (last_activity_at);
CREATE INDEX ix_carts_email ON carts (email) WHERE email IS NOT NULL;

-- ---------------------------------------------------------------------------------------------
-- Payments (charges and refunds), order timeline
-- ---------------------------------------------------------------------------------------------
CREATE TABLE payments (
    id            BIGSERIAL PRIMARY KEY,
    order_id      BIGINT NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    provider      VARCHAR(20) NOT NULL,
    kind          VARCHAR(10) NOT NULL DEFAULT 'charge',
    status        VARCHAR(12) NOT NULL DEFAULT 'pending',
    amount        NUMERIC(12, 2) NOT NULL,
    currency      VARCHAR(3) NOT NULL DEFAULT 'USD',
    provider_ref  VARCHAR(255),
    error         TEXT,
    raw           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_id BIGINT REFERENCES users (id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_payments_kind CHECK (kind IN ('charge', 'refund')),
    CONSTRAINT ck_payments_status CHECK (status IN ('pending', 'succeeded', 'failed', 'cancelled'))
);
CREATE INDEX ix_payments_order_id ON payments (order_id);
CREATE INDEX ix_payments_provider_ref ON payments (provider_ref) WHERE provider_ref IS NOT NULL;

CREATE TABLE order_events (
    id         BIGSERIAL PRIMARY KEY,
    order_id   BIGINT NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    type       VARCHAR(30) NOT NULL,
    message    TEXT,
    data       JSONB NOT NULL DEFAULT '{}'::jsonb,
    actor_id   BIGINT REFERENCES users (id) ON DELETE SET NULL,
    actor      VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_order_events_order_id ON order_events (order_id, created_at);

-- ---------------------------------------------------------------------------------------------
-- Email outbox (transactional and marketing mail; a cron job sends and retries)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE email_outbox (
    id           BIGSERIAL PRIMARY KEY,
    to_email     VARCHAR(320) NOT NULL,
    kind         VARCHAR(30) NOT NULL,
    subject      VARCHAR(300) NOT NULL,
    body_text    TEXT NOT NULL,
    body_html    TEXT,
    locale       VARCHAR(5),
    status       VARCHAR(10) NOT NULL DEFAULT 'queued',
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT,
    related_type VARCHAR(20),
    related_id   BIGINT,
    send_after   TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_email_outbox_status CHECK (status IN ('queued', 'sent', 'failed', 'skipped'))
);
CREATE INDEX ix_email_outbox_due ON email_outbox (status, send_after);
CREATE INDEX ix_email_outbox_related ON email_outbox (related_type, related_id);

-- ---------------------------------------------------------------------------------------------
-- Audit log (who changed what in the admin)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor_id    BIGINT REFERENCES users (id) ON DELETE SET NULL,
    actor_email VARCHAR(320),
    action      VARCHAR(60) NOT NULL,
    entity_type VARCHAR(30),
    entity_id   VARCHAR(40),
    summary     VARCHAR(500),
    data        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_log_created ON audit_log (created_at DESC);
CREATE INDEX ix_audit_log_entity ON audit_log (entity_type, entity_id);
