-- The supplier list: listings, orders and supplier logins pick a supplier from here instead of typing a name.
-- Orders, listings and logins keep the supplier *name* (as before); renaming a supplier updates them all.
CREATE TABLE suppliers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    contact_name VARCHAR(200),
    email VARCHAR(320),
    phone VARCHAR(50),
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_suppliers_name_lower ON suppliers (lower(name));

-- Every name already in use becomes a supplier (first spelling wins; case doesn't make two suppliers).
INSERT INTO suppliers (name)
SELECT DISTINCT ON (lower(n)) n FROM (
    SELECT btrim(supplier) AS n FROM etsy_orders WHERE supplier IS NOT NULL AND btrim(supplier) <> ''
    UNION ALL SELECT btrim(internal_supplier) FROM etsy_listings WHERE internal_supplier IS NOT NULL AND btrim(internal_supplier) <> ''
    UNION ALL SELECT btrim(supplier_name) FROM users WHERE supplier_name IS NOT NULL AND btrim(supplier_name) <> ''
) names ORDER BY lower(n), n;
