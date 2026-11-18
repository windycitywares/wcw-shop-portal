DROP INDEX ix_etsy_orders_supplier_paid_at;
ALTER TABLE etsy_orders DROP COLUMN supplier_paid_by;
ALTER TABLE etsy_orders DROP COLUMN supplier_payment_ref;
ALTER TABLE etsy_orders DROP COLUMN supplier_paid_amount;
ALTER TABLE etsy_orders DROP COLUMN supplier_paid_at;
