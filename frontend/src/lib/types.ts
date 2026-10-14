// Mirrors the API schemas in backend/app/schemas.

export type Role = "admin" | "publisher" | "author" | "customer";
export type ContentStatus = "draft" | "in_review" | "published" | "archived";
export type StockStatus = "in_stock" | "out_of_stock" | "backorder" | "preorder";
export type AttributeValue = string | number | boolean | Array<string | number>;

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Category {
  id: number;
  parent_id: number | null;
  name: string;
  slug: string;
  description: string | null;
  image_url: string | null;
  sort_order: number;
  is_active: boolean;
  depth: number;
}

export interface CategoryNode extends Category {
  children: CategoryNode[];
}

export interface CategoryDetail extends Category {
  breadcrumb: Category[];
  children: Category[];
}

export interface ProductImage {
  url: string;
  alt: string | null;
}

export interface Product {
  id: number;
  parent_id: number | null;
  category_id: number | null;
  sku: string;
  slug: string;
  title: string;
  description: string | null;
  base_price: number;
  compare_at_price: number | null;
  currency: string;
  stock_status: StockStatus;
  stock_quantity: number | null;
  attributes: Record<string, AttributeValue>;
  images: ProductImage[];
  tags: string[];
  status: ContentStatus;
  source: string;
  seo_title: string | null;
  seo_description: string | null;
  created_by_id: number | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  /** Set while a sale is live: the price to charge instead of base_price. */
  sale_price: number | null;
  sale_label: string | null;
  sale_ends_at: string | null;
}

export interface ProductDetail extends Product {
  variants: Product[];
  category: Category | null;
  breadcrumb: Category[];
}

export interface Facets {
  price_min: number | null;
  price_max: number | null;
  attributes: { key: string; values: { value: string; count: number }[] }[];
}

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
  permissions: string[];
}

export interface ImporterInfo {
  key: string;
  label: string;
  description: string;
  accepted_extensions: string[];
}

export interface ImportPreview {
  source: string;
  total: number;
  warnings: string[];
  rows: {
    row: number;
    sku: string | null;
    title: string;
    price: number;
    quantity: number | null;
    images: number;
    variants: number;
    category: string | null;
    attributes: Record<string, AttributeValue>;
  }[];
}

export interface ImportSummary {
  source: string;
  created: number;
  updated: number;
  skipped: number;
  variants: number;
  errors: { row: number; title: string | null; error: string }[];
  warnings: string[];
}

// ---- shop: settings, cart quote and orders -------------------------------------------------

export type PaymentProvider = "stripe" | "offline" | "test";

export interface PaymentOption {
  id: PaymentProvider;
  label: string;
  description: string | null;
}

export interface WelcomeOffer {
  kind: "percent" | "fixed";
  value: number;
  min_subtotal: number;
}

export interface ShopConfig {
  currency: string;
  checkout_enabled: boolean;
  payment_options: PaymentOption[];
  free_shipping_threshold: number | null;
  /** Countries we ship to; null = everywhere. */
  shipping_countries: string[] | null;
  welcome_offer: WelcomeOffer | null;
}

export interface QuoteLine {
  key: string | null;
  product_id: number;
  quantity: number;
  list_price: number;
  unit_price: number;
  line_total: number;
  discount: number;
  sale_label: string | null;
  issue: "sold_out" | "limited" | null;
  max_quantity: number | null;
}

export interface QuoteProblem {
  code: string;
  message: string;
  data: Record<string, string>;
}

export interface ShippingOption {
  code: string;
  name: string;
  description: string | null;
  base_price: number;
  price: number;
  free: boolean;
  min_days: number | null;
  max_days: number | null;
}

export interface TaxLine {
  name: string;
  rate: number;
  amount: number;
}

export interface Quote {
  currency: string;
  lines: QuoteLine[];
  unavailable: number[];
  list_subtotal: number;
  sale_savings: number;
  subtotal: number;
  coupon: { code: string; discount: number; free_shipping: boolean } | null;
  coupon_problem: QuoteProblem | null;
  shipping_options: ShippingOption[];
  shipping_method: string | null;
  shipping_total: number;
  shipping_discount: number;
  tax_lines: TaxLine[];
  tax_total: number;
  total: number;
  free_shipping_threshold: number | null;
  free_shipping_remaining: number | null;
}

export type OrderStatus = "pending" | "paid" | "processing" | "shipped" | "delivered" | "cancelled" | "refunded";

export interface OrderAddress {
  full_name: string;
  company?: string | null;
  line1: string;
  line2?: string | null;
  city: string;
  region?: string | null;
  postal_code: string;
  country: string;
  phone?: string | null;
}

export interface OrderItem {
  id: number;
  product_id: number | null;
  sku: string;
  title: string;
  unit_price: number;
  list_price: number | null;
  quantity: number;
  line_total: number;
  discount: number;
  attributes: Record<string, AttributeValue>;
}

export interface OrderEvent {
  id: number;
  kind: string;
  message: string;
  created_at: string;
}

export interface OrderRefund {
  id: number;
  amount: number;
  reason: string | null;
  restocked: boolean;
  created_at: string;
}

export interface Order {
  number: string;
  status: OrderStatus;
  fulfillment_status: string;
  email: string;
  currency: string;
  subtotal: number;
  sale_savings: number;
  discount_total: number;
  shipping_total: number;
  shipping_discount: number;
  tax_total: number;
  /** Stored as text by the API, e.g. { name: "Illinois sales tax", rate: "6.250", amount: "3.12" } */
  tax_lines: { name: string; rate: string | number; amount: string | number }[];
  grand_total: number;
  refunded_total: number;
  coupon_code: string | null;
  shipping_address: OrderAddress | null;
  billing_address: OrderAddress | null;
  shipping_method: string | null;
  carrier: string | null;
  tracking_number: string | null;
  payment_provider: PaymentProvider | null;
  payment_instructions: string | null;
  notes: string | null;
  placed_at: string | null;
  paid_at: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  cancelled_at: string | null;
  items: OrderItem[];
  events: OrderEvent[];
  refunds: OrderRefund[];
  // Staff only (null for customers)
  id: number | null;
  user_id: number | null;
  internal_note: string | null;
  payment_ref: string | null;
  locale: string | null;
}

export interface OrderListItem {
  number: string;
  status: OrderStatus;
  fulfillment_status: string;
  email: string;
  customer: string | null;
  grand_total: number;
  refunded_total: number;
  item_count: number;
  payment_provider: PaymentProvider | null;
  coupon_code: string | null;
  placed_at: string | null;
}

export interface OrderPlaced {
  number: string;
  access_token: string;
  status: OrderStatus;
  total: number;
  next: "paid" | "pay" | "offline";
  payment_url: string | null;
  instructions: string | null;
}

// ---- admin: store settings, promotions and the inbox ---------------------------------------

export interface ReadinessItem {
  id: string;
  ok: boolean;
  required: boolean;
  text: string;
}

export interface StoreSettings {
  checkout_enabled: boolean;
  offline_enabled: boolean;
  offline_label: string;
  offline_instructions: string;
  stripe_enabled: boolean;
  low_stock_threshold: number;
  welcome_enabled: boolean;
  welcome_kind: "percent" | "fixed";
  /** Decimal values arrive as text. */
  welcome_value: string;
  welcome_valid_days: number;
  welcome_min_subtotal: string;
  order_alert_email: string | null;
  stripe_configured: boolean;
  test_payments_available: boolean;
  readiness: ReadinessItem[];
}

export interface ShippingMethod {
  id: number;
  code: string;
  name: string;
  description: string | null;
  price: number;
  free_over: number | null;
  min_days: number | null;
  max_days: number | null;
  countries: string[];
  is_active: boolean;
  sort_order: number;
}

export interface TaxRate {
  id: number;
  name: string;
  country: string;
  region: string | null;
  rate: number;
  applies_to_shipping: boolean;
  is_active: boolean;
}

export type DiscountScope = "all" | "category" | "products";
export type CouponKind = "percent" | "fixed" | "free_shipping";
export type CouponStatus = "active" | "scheduled" | "expired" | "used_up" | "paused";

export interface Coupon {
  id: number;
  code: string;
  description: string | null;
  kind: CouponKind;
  value: number;
  min_subtotal: number | null;
  max_discount: number | null;
  scope: DiscountScope;
  category_id: number | null;
  product_ids: number[];
  exclude_sale_items: boolean;
  first_order_only: boolean;
  usage_limit: number | null;
  per_customer_limit: number | null;
  used_count: number;
  starts_at: string | null;
  expires_at: string | null;
  is_active: boolean;
  user_id: number | null;
  email: string | null;
  issued_to: string | null;
  campaign: string | null;
  source: "manual" | "generated" | "welcome" | "personal";
  created_at: string;
  status: CouponStatus;
  discount_given: number;
  orders: number;
}

export interface Campaign {
  campaign: string;
  codes: number;
  used: number;
  discount_given: number;
  created_at: string;
}

export interface Sale {
  id: number;
  name: string;
  label: string | null;
  kind: "percent" | "fixed";
  value: number;
  scope: DiscountScope;
  category_id: number | null;
  product_ids: number[];
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
  created_at: string;
  status: "live" | "scheduled" | "ended" | "paused";
  category_name: string | null;
  products: string[];
}

export interface InboxMessage {
  id: number;
  name: string;
  email: string;
  subject: string;
  message: string;
  order_number: string | null;
  locale: string | null;
  user_id: number | null;
  status: "new" | "answered" | "archived";
  admin_note: string | null;
  emailed: boolean;
  handled_at: string | null;
  created_at: string;
}
