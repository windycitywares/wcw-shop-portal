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
