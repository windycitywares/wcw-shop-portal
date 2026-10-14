/** Shapes of /admin/orders (backend/app/schemas/orders.py). */

export interface OrderListItem {
  id: number;
  number: string;
  email: string;
  customer_name: string | null;
  status: string;
  payment_status: string;
  fulfillment_status: string;
  payment_provider: string | null;
  grand_total: number;
  refunded_total: number;
  coupon_code: string | null;
  channel: string | null;
  item_count: number;
  placed_at: string | null;
  paid_at: string | null;
}

export interface OrderList {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
  stats: { orders: number; revenue: number; open_orders: number };
}

export interface OrderItem {
  id: number;
  product_id: number | null;
  slug: string | null;
  sku: string;
  title: string;
  image_url: string | null;
  unit_price: number;
  list_price: number | null;
  quantity: number;
  line_total: number;
  discount_total: number;
  attributes: Record<string, unknown>;
  unit_cost: number | null;
  refunded_quantity: number;
  sale_id: number | null;
}

export interface OrderDetail extends Omit<OrderListItem, "item_count"> {
  phone: string | null;
  currency: string;
  subtotal: number;
  discount_total: number;
  shipping_total: number;
  tax_total: number;
  tax_rate: number;
  discounts: { type: string; label: string; code: string | null; amount: number }[];
  shipping_address: Record<string, string | null> | null;
  billing_address: Record<string, string | null> | null;
  shipping_method: string | null;
  carrier: string | null;
  tracking_number: string | null;
  tracking_url: string | null;
  notes: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  cancelled_at: string | null;
  items: OrderItem[];
  user_id: number | null;
  locale: string | null;
  device: string | null;
  marketing_opt_in: boolean;
  payments: { id: number; provider: string; kind: string; status: string; amount: number; provider_ref: string | null; error: string | null; created_at: string }[];
  events: { id: number; type: string; message: string | null; actor: string | null; created_at: string }[];
  customer_order_count: number;
  cost_total: number | null;
  profit: number | null;
}

export const PAYMENT_LABEL: Record<string, string> = {
  unpaid: "Unpaid",
  paid: "Paid",
  partially_refunded: "Partly refunded",
  refunded: "Refunded",
};

export const PROVIDER_LABEL: Record<string, string> = { stripe: "Card (Stripe)", manual: "Pay later", test: "Test payment" };
