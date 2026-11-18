-- Orders that were already shipped (or cancelled) when Etsy was first connected are kept for history and reports, but they
-- don't need attention (owner's decision, 2026-11-17). Costs can still be added to them.
ALTER TABLE etsy_orders ADD COLUMN past_order BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE etsy_orders SET past_order = TRUE WHERE status IN ('shipped', 'delivered', 'closed', 'cancelled');
