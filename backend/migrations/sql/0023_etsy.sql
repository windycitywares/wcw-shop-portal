-- Etsy → shop (see docs/ETSY.md). Etsy is the source of truth for listings and orders; the team adds costs, supplier and
-- tracking on top. Everything here is separate from the storefront's own products/orders on purpose.

-- The one connection to the Etsy shop (a single row, id = 1). Tokens are encrypted (app/core/secretbox.py).
CREATE TABLE etsy_connection (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    etsy_shop_id BIGINT,
    shop_name VARCHAR(200),
    access_token TEXT,                      -- encrypted
    refresh_token TEXT,                     -- encrypted
    token_expires_at TIMESTAMPTZ,
    scopes VARCHAR(500),
    connected_at TIMESTAMPTZ,
    connected_by_id BIGINT,
    oauth_state VARCHAR(100),               -- the one-time value that comes back to us from Etsy's "Allow access" screen
    oauth_verifier VARCHAR(200),            -- PKCE, encrypted at rest with the tokens
    listings_synced_at TIMESTAMPTZ,
    orders_synced_at TIMESTAMPTZ,
    last_error VARCHAR(500),                -- why the last sync failed (cleared by a good one); drives the "connection lost" alert
    last_error_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Etsy listings, read-only mirror. Only the three internal_* columns are the team's.
CREATE TABLE etsy_listings (
    id BIGSERIAL PRIMARY KEY,
    etsy_listing_id BIGINT NOT NULL UNIQUE,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    state VARCHAR(20) NOT NULL DEFAULT 'active',   -- active | inactive | sold_out | draft | expired
    price NUMERIC(12,2),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    quantity INTEGER,
    skus JSONB NOT NULL DEFAULT '[]',
    url VARCHAR(500),
    images JSONB NOT NULL DEFAULT '[]',
    variations JSONB NOT NULL DEFAULT '[]',        -- [{"name": "Size", "values": ["S","M"]}] and each offering's price/stock
    tags JSONB NOT NULL DEFAULT '[]',
    etsy_updated_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    internal_supplier VARCHAR(200),                -- default supplier for new orders of this listing
    internal_purchase_cost NUMERIC(12,2),          -- default purchase cost per unit
    internal_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_etsy_listings_state ON etsy_listings (state);

-- One row per Etsy order ("receipt"). Money columns copy what Etsy charged; the cost columns are the team's.
CREATE TABLE etsy_orders (
    id BIGSERIAL PRIMARY KEY,
    etsy_receipt_id BIGINT NOT NULL UNIQUE,        -- the Etsy order number
    status VARCHAR(20) NOT NULL DEFAULT 'new',     -- see app/domain/etsy_status.py
    etsy_state VARCHAR(30),                        -- Etsy's own word: paid, completed, canceled …
    ordered_at TIMESTAMPTZ NOT NULL,
    paid_at TIMESTAMPTZ,
    ship_by TIMESTAMPTZ,                           -- Etsy's expected ship date
    buyer_name VARCHAR(200),
    etsy_buyer_id BIGINT,
    buyer_email VARCHAR(320),                      -- often hidden by Etsy: the system must work without it
    buyer_phone VARCHAR(50),                       -- never from Etsy; typed in by the team
    ship_address JSONB NOT NULL DEFAULT '{}',
    gift_message TEXT,
    buyer_note TEXT,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    items_total NUMERIC(12,2) NOT NULL DEFAULT 0,  -- the items, before discounts
    shipping_charged NUMERIC(12,2) NOT NULL DEFAULT 0,
    discounts NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax NUMERIC(12,2) NOT NULL DEFAULT 0,
    grand_total NUMERIC(12,2) NOT NULL DEFAULT 0,
    etsy_fees NUMERIC(12,2),                       -- the real fees from Etsy's ledger (phase 2); NULL = not fetched yet
    etsy_fees_at TIMESTAMPTZ,
    purchase_cost NUMERIC(12,2),                   -- the team's: what we paid the supplier (NULL = not entered)
    costs_prefilled BOOLEAN NOT NULL DEFAULT FALSE,-- the cost above came from the listings' default costs, not typed in
    supplier VARCHAR(200),
    supplier_order_number VARCHAR(100),
    shipping_cost NUMERIC(12,2),                   -- what shipping actually cost us
    carrier VARCHAR(60),
    tracking_number VARCHAR(100),
    tracking_sent_at TIMESTAMPTZ,                  -- phase 2: when it reached Etsy
    tracking_error VARCHAR(300),
    purchased_at TIMESTAMPTZ,
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    notes TEXT,
    etsy_updated_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_etsy_orders_status ON etsy_orders (status);
CREATE INDEX ix_etsy_orders_ordered_at ON etsy_orders (ordered_at);

CREATE TABLE etsy_order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES etsy_orders (id) ON DELETE CASCADE,
    etsy_transaction_id BIGINT NOT NULL UNIQUE,
    etsy_listing_id BIGINT,                        -- loose link to etsy_listings (the listing may be gone from Etsy)
    title VARCHAR(300) NOT NULL,
    sku VARCHAR(100),
    variations JSONB NOT NULL DEFAULT '[]',
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0
);
CREATE INDEX ix_etsy_order_items_order_id ON etsy_order_items (order_id);
CREATE INDEX ix_etsy_order_items_etsy_listing_id ON etsy_order_items (etsy_listing_id);

-- The order's history: every status change, cost or tracking edit, with who and when ("etsy" for what the sync did).
CREATE TABLE etsy_order_events (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES etsy_orders (id) ON DELETE CASCADE,
    kind VARCHAR(20) NOT NULL,                     -- created | status | costs | tracking | note | sync
    from_status VARCHAR(20),
    to_status VARCHAR(20),
    message VARCHAR(500) NOT NULL,
    source VARCHAR(10) NOT NULL DEFAULT 'team',    -- team | etsy
    actor_id BIGINT,
    actor_name VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_etsy_order_events_order_id ON etsy_order_events (order_id, id);
