-- The CRM becomes the place suppliers are managed (docs/ETSY.md → "Suppliers"). Each shop supplier remembers the CRM
-- record it mirrors; once any supplier is linked, the shop's list is read-only and changes arrive from the CRM.
ALTER TABLE suppliers ADD COLUMN crm_id BIGINT;
ALTER TABLE suppliers ADD COLUMN crm_synced_at TIMESTAMPTZ;
CREATE UNIQUE INDEX uq_suppliers_crm_id ON suppliers (crm_id) WHERE crm_id IS NOT NULL;
