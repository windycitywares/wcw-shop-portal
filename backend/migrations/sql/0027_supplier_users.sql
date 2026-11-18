-- Supplier logins: a supplier signs in to see and ship only their own orders, on the external shops an admin allowed.
-- (IF NOT EXISTS: the value survives a downgrade — PostgreSQL can't drop an enum value — so upgrading again must not fail.)
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'supplier';
ALTER TABLE users ADD COLUMN supplier_name VARCHAR(200);
ALTER TABLE users ADD COLUMN supplier_channels JSONB NOT NULL DEFAULT '[]'::jsonb;
