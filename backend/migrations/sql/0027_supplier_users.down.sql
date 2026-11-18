-- The 'supplier' enum value stays (PostgreSQL can't drop one); supplier logins become plain customers with no access.
UPDATE users SET role = 'customer', is_active = FALSE WHERE role = 'supplier';
ALTER TABLE users DROP COLUMN supplier_channels;
ALTER TABLE users DROP COLUMN supplier_name;
