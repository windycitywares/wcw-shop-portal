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
  rating_avg?: number;
  rating_count?: number;
  /** Set while a sale is running (computed by the API, not stored). */
  sale_price?: number | null;
  sale_label?: string | null;
  sale_ends_at?: string | null;
  badges?: ProductBadge[];
}

export type ProductBadge = "sale" | "best_seller" | "new" | "low_stock";

/** Store settings the storefront needs (GET /shop/config). */
export interface ShopConfig {
  currency: string;
  free_shipping_threshold: number | null;
  flat_shipping_rate: number;
  international_shipping: boolean;
  shipping_countries: string[];
  delivery_days: [number, number];
  handling_days?: [number, number];
  transit_days?: [number, number];
  tax_enabled: boolean;
  tax_label: string;
  announcement: string | null;
  welcome_percent: number | null;
  payment_methods: string[];
  guest_checkout: boolean;
  max_quantity_per_line: number;
  low_stock_threshold: number;
  analytics_enabled: boolean;
  turnstile_site_key: string | null;
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

/** POST /cart/quote — the cart priced by the server (the same rules checkout uses). */
export interface QuoteLine {
  product_id: number;
  parent_id: number | null;
  slug: string;
  sku: string;
  title: string;
  variant: string | null;
  image: string | null;
  options: Record<string, string>;
  quantity: number;
  unit_price: number;
  list_price: number;
  line_total: number;
  line_discount: number;
  on_sale: boolean;
  sale_label: string | null;
  stock_left: number | null;
}

export interface Quote {
  currency: string;
  lines: QuoteLine[];
  item_count: number;
  subtotal: number;
  list_subtotal: number;
  sale_savings: number;
  discounts: { type: "rule" | "coupon" | "free_shipping"; label: string; amount: number; code: string | null }[];
  discount_total: number;
  shipping: {
    amount: number;
    free: boolean;
    reason: string;
    free_threshold: number | null;
    remaining_for_free: number | null;
    deliverable: boolean;
  };
  tax: { label: string; rate_percent: number; amount: number } | null;
  tax_pending: boolean;
  total: number;
  coupon: { code: string; valid: boolean; applied: boolean; message: string | null; reason: string | null } | null;
  rewards: { name: string; kind: string; value: number; remaining_amount: number | null; remaining_qty: number | null }[];
  messages: string[];
  blocking: boolean;
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

/** An order as its owner sees it (private link or account page). */
export interface PublicOrder {
  id: number;
  number: string;
  email: string;
  customer_name: string | null;
  status: OrderStatus;
  payment_status: string;
  fulfillment_status: string;
  currency: string;
  subtotal: number;
  discount_total: number;
  shipping_total: number;
  tax_total: number;
  grand_total: number;
  refunded_total: number;
  coupon_code: string | null;
  discounts: { type: string; label: string; code: string | null; amount: number }[];
  shipping_address: OrderAddress | null;
  carrier: string | null;
  tracking_number: string | null;
  tracking_url: string | null;
  payment_provider: string | null;
  notes: string | null;
  placed_at: string | null;
  paid_at: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  cancelled_at: string | null;
  items: {
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
  }[];
  timeline: { type: string; message: string | null; created_at: string }[];
  access_token: string | null;
}

export interface PaymentAction {
  provider: string;
  status: "paid" | "pending" | "redirect";
  redirect_url: string | null;
  instructions: string | null;
}

export interface CheckoutResult {
  order: PublicOrder;
  payment: PaymentAction;
}

/** Compact product (wishlist, also bought, recently viewed). */
export interface ProductCardData {
  id: number;
  slug: string;
  title: string;
  base_price: number;
  sale_price: number | null;
  compare_at_price: number | null;
  image: string | null;
}
