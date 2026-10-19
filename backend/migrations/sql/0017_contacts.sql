-- Contacts: anyone the shop has a relationship with (a superset of customers and users), importable into the CRM.
CREATE TABLE contacts (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    full_name VARCHAR(200),
    phone VARCHAR(40),
    -- where we met them: signup, order, newsletter, contact_form, stock_alert, import
    source VARCHAR(32) NOT NULL DEFAULT 'import',
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_contacts_email ON contacts (email);
CREATE INDEX ix_contacts_user_id ON contacts (user_id);

-- Backfill from the sources we already have. Email is the key; the first source to claim an address wins
-- the name/phone, the rest just make sure the row exists.
INSERT INTO contacts (email, full_name, phone, source, user_id, marketing_opt_in, created_at)
SELECT lower(u.email), u.full_name, NULL, 'signup', u.id, FALSE, u.created_at
FROM users u
WHERE u.role = 'customer'
ON CONFLICT (email) DO NOTHING;

INSERT INTO contacts (email, full_name, phone, source, marketing_opt_in, created_at)
SELECT lower(ns.email), NULL, NULL, 'newsletter', TRUE, ns.created_at
FROM newsletter_subscribers ns
ON CONFLICT (email) DO NOTHING;

INSERT INTO contacts (email, full_name, phone, source, created_at)
SELECT lower(cm.email), cm.name, NULL, 'contact_form', cm.created_at
FROM contact_messages cm
ON CONFLICT (email) DO NOTHING;

INSERT INTO contacts (email, full_name, phone, source, created_at)
SELECT lower(sa.email), NULL, NULL, 'stock_alert', sa.created_at
FROM stock_alerts sa
ON CONFLICT (email) DO NOTHING;

INSERT INTO contacts (email, full_name, phone, source, created_at)
SELECT DISTINCT ON (lower(o.email)) lower(o.email), o.customer_name, o.phone, 'order', o.placed_at
FROM orders o
WHERE o.email IS NOT NULL
ORDER BY lower(o.email), o.placed_at
ON CONFLICT (email) DO NOTHING;
