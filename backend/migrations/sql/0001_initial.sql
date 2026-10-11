-- Initial schema for Windy City Wares. Mirrors app/models/*.
CREATE EXTENSION IF NOT EXISTS ltree;

CREATE TYPE user_role AS ENUM ('admin', 'publisher', 'author', 'customer');
CREATE TYPE content_status AS ENUM ('draft', 'in_review', 'published', 'archived');
CREATE TYPE stock_status AS ENUM ('in_stock', 'out_of_stock', 'backorder', 'preorder');
CREATE TYPE order_status AS ENUM ('pending', 'paid', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded');
CREATE TYPE fulfillment_status AS ENUM ('unfulfilled', 'partial', 'fulfilled', 'returned');

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(320) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(200),
    role            user_role NOT NULL DEFAULT 'customer',
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE TABLE newsletter_subscribers (
    id         BIGSERIAL PRIMARY KEY,
    email      VARCHAR(320) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_newsletter_subscribers_email UNIQUE (email)
);

CREATE TABLE categories (
    id          BIGSERIAL PRIMARY KEY,
    parent_id   BIGINT REFERENCES categories (id) ON DELETE RESTRICT,
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(220) NOT NULL,
    description TEXT,
    image_url   VARCHAR(1000),
    path        LTREE NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_categories_slug UNIQUE (slug)
);
CREATE INDEX ix_categories_parent_id ON categories (parent_id);
CREATE INDEX ix_categories_path_gist ON categories USING GIST (path);

CREATE TABLE products (
    id               BIGSERIAL PRIMARY KEY,
    parent_id        BIGINT REFERENCES products (id) ON DELETE CASCADE,
    category_id      BIGINT REFERENCES categories (id) ON DELETE SET NULL,
    sku              VARCHAR(100) NOT NULL,
    slug             VARCHAR(255) NOT NULL,
    title            VARCHAR(300) NOT NULL,
    description      TEXT,
    base_price       NUMERIC(12, 2) NOT NULL,
    compare_at_price NUMERIC(12, 2),
    currency         VARCHAR(3) NOT NULL DEFAULT 'USD',
    stock_status     stock_status NOT NULL DEFAULT 'in_stock',
    stock_quantity   INTEGER,
    attributes       JSONB NOT NULL DEFAULT '{}'::jsonb,
    images           JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags             TEXT[] NOT NULL DEFAULT '{}'::text[],
    status           content_status NOT NULL DEFAULT 'draft',
    source           VARCHAR(30) NOT NULL DEFAULT 'manual',
    source_ref       VARCHAR(255),
    seo_title        VARCHAR(300),
    seo_description  VARCHAR(500),
    created_by_id    BIGINT REFERENCES users (id) ON DELETE SET NULL,
    published_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_products_sku UNIQUE (sku),
    CONSTRAINT uq_products_slug UNIQUE (slug),
    CONSTRAINT ck_products_price_nonneg CHECK (base_price >= 0)
);
CREATE INDEX ix_products_parent_id ON products (parent_id);
CREATE INDEX ix_products_category_id ON products (category_id);
CREATE INDEX ix_products_status ON products (status);
CREATE UNIQUE INDEX uq_products_source_ref ON products (source, source_ref) WHERE source_ref IS NOT NULL;
CREATE INDEX ix_products_attributes ON products USING GIN (attributes jsonb_path_ops);

CREATE TABLE orders (
    id                 BIGSERIAL PRIMARY KEY,
    number             VARCHAR(32) NOT NULL,
    user_id            BIGINT REFERENCES users (id) ON DELETE SET NULL,
    email              VARCHAR(320) NOT NULL,
    status             order_status NOT NULL DEFAULT 'pending',
    fulfillment_status fulfillment_status NOT NULL DEFAULT 'unfulfilled',
    currency           VARCHAR(3) NOT NULL DEFAULT 'USD',
    subtotal           NUMERIC(12, 2) NOT NULL DEFAULT 0,
    tax_total          NUMERIC(12, 2) NOT NULL DEFAULT 0,
    shipping_total     NUMERIC(12, 2) NOT NULL DEFAULT 0,
    discount_total     NUMERIC(12, 2) NOT NULL DEFAULT 0,
    grand_total        NUMERIC(12, 2) NOT NULL DEFAULT 0,
    shipping_address   JSONB,
    billing_address    JSONB,
    shipping_method    VARCHAR(100),
    tracking_number    VARCHAR(100),
    payment_provider   VARCHAR(30),
    payment_intent_id  VARCHAR(255),
    notes              TEXT,
    placed_at          TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_orders_number UNIQUE (number)
);
CREATE INDEX ix_orders_user_id ON orders (user_id);
CREATE INDEX ix_orders_payment_intent_id ON orders (payment_intent_id);

CREATE TABLE order_items (
    id         BIGSERIAL PRIMARY KEY,
    order_id   BIGINT NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES products (id) ON DELETE SET NULL,
    sku        VARCHAR(100) NOT NULL,
    title      VARCHAR(300) NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    quantity   INTEGER NOT NULL,
    line_total NUMERIC(12, 2) NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_order_items_quantity_positive CHECK (quantity > 0)
);
CREATE INDEX ix_order_items_order_id ON order_items (order_id);
