-- Reverses 0006_commerce.sql
DROP TABLE audit_log;
DROP TABLE email_outbox;
DROP TABLE order_events;
DROP TABLE payments;
DROP TABLE carts;
DROP TABLE cart_rules;
DROP TABLE coupon_redemptions;
DROP TABLE coupons;
DROP TABLE sales;
DROP TABLE store_settings;
DROP INDEX ix_order_items_product_id;
DROP INDEX ix_orders_placed_at;
DROP INDEX ix_orders_status;
DROP INDEX ix_orders_email;
ALTER TABLE order_items DROP COLUMN slug, DROP COLUMN image_url, DROP COLUMN list_price, DROP COLUMN unit_cost, DROP COLUMN sale_id, DROP COLUMN discount_total, DROP COLUMN refunded_quantity;
ALTER TABLE orders DROP COLUMN access_token, DROP COLUMN customer_name, DROP COLUMN phone, DROP COLUMN locale, DROP COLUMN payment_status, DROP COLUMN refunded_total, DROP COLUMN coupon_code, DROP COLUMN discounts, DROP COLUMN tax_rate, DROP COLUMN carrier, DROP COLUMN tracking_url, DROP COLUMN session_id, DROP COLUMN channel, DROP COLUMN device, DROP COLUMN idempotency_key, DROP COLUMN marketing_opt_in, DROP COLUMN paid_at, DROP COLUMN shipped_at, DROP COLUMN delivered_at, DROP COLUMN cancelled_at, DROP COLUMN review_requested_at;
DROP SEQUENCE order_number_seq;
ALTER TABLE products DROP COLUMN cost_price, DROP COLUMN units_sold;
