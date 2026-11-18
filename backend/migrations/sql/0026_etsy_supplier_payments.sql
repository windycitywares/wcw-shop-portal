-- Paying suppliers for Etsy orders: an order is "pending" once its purchase cost is entered and "settled" when an admin
-- records the payment (amount, date, reference). Original costs are never changed by a payment.
ALTER TABLE etsy_orders ADD COLUMN supplier_paid_at TIMESTAMPTZ;
ALTER TABLE etsy_orders ADD COLUMN supplier_paid_amount NUMERIC(12,2);
ALTER TABLE etsy_orders ADD COLUMN supplier_payment_ref VARCHAR(100);
ALTER TABLE etsy_orders ADD COLUMN supplier_paid_by VARCHAR(200);
CREATE INDEX ix_etsy_orders_supplier_paid_at ON etsy_orders (supplier_paid_at);
