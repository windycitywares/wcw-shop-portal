DROP INDEX uq_suppliers_crm_id;
ALTER TABLE suppliers DROP COLUMN crm_synced_at;
ALTER TABLE suppliers DROP COLUMN crm_id;
