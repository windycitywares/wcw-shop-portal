/**
 * Server-side data access (Server Components, sitemap, metadata).
 * Storefront reads are cached and revalidated every few minutes.
 * Network failures degrade to empty results so pages still render.
 */
import "server-only";
import { defaultLocale, type Locale } from "@/i18n/config";
import type { CategoryDetail, CategoryNode, Facets, Page, Product, ProductCardData, ProductDetail, ShopConfig } from "./types";

const API_URL = (
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000/api/v1"
).replace(/\/$/, "");

const REVALIDATE_SECONDS = 300;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(path: string, revalidate = REVALIDATE_SECONDS): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    next: { revalidate },
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed with ${res.status}`);
  return (await res.json()) as T;
}

/** Adds ?lang= for non-English requests (the API falls back to English per field). */
function withLang(path: string, lang?: Locale): string {
  if (!lang || lang === defaultLocale) return path;
  return `${path}${path.includes("?") ? "&" : "?"}lang=${lang}`;
}

const EMPTY_PAGE: Page<Product> = { items: [], total: 0, page: 1, page_size: 24 };

export async function getCategoryTree(lang?: Locale): Promise<CategoryNode[]> {
  try {
    return await get<CategoryNode[]>(withLang("/categories/tree", lang));
  } catch {
    return [];
  }
}

export async function getCategory(slug: string, lang?: Locale): Promise<CategoryDetail | null> {
  try {
    return await get<CategoryDetail>(withLang(`/categories/${encodeURIComponent(slug)}`, lang));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function getProducts(
  params: URLSearchParams | Record<string, string>,
  lang?: Locale,
): Promise<Page<Product>> {
  const qs = new URLSearchParams(params).toString();
  try {
    return await get<Page<Product>>(withLang(`/products${qs ? `?${qs}` : ""}`, lang), 60);
  } catch {
    return EMPTY_PAGE;
  }
}

export async function getProduct(slug: string, lang?: Locale): Promise<ProductDetail | null> {
  try {
    return await get<ProductDetail>(withLang(`/products/${encodeURIComponent(slug)}`, lang), 60);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function getFacets(category?: string): Promise<Facets> {
  try {
    return await get<Facets>(`/products/facets${category ? `?category=${encodeURIComponent(category)}` : ""}`);
  } catch {
    return { price_min: null, price_max: null, attributes: [] };
  }
}

/** First photo and design count for a category (home page theme tiles). */
export async function getCategoryPreview(slug: string): Promise<{ total: number; image: string | null }> {
  const res = await getProducts({ category: slug, page_size: "1", sort: "newest" });
  return { total: res.total, image: res.items[0]?.images[0]?.url ?? null };
}

/** All published products (for the sitemap). */
export async function getAllProducts(max = 5000): Promise<Product[]> {
  const out: Product[] = [];
  for (let page = 1; out.length < max; page++) {
    const res = await getProducts({ page: String(page), page_size: "100", sort: "updated" });
    out.push(...res.items);
    if (res.items.length < 100) break;
  }
  return out;
}

/** Store settings for the storefront (shipping promise, banner, payment choices). Null when the API is unreachable. */
export async function getShopConfig(lang?: Locale): Promise<ShopConfig | null> {
  try {
    return await get<ShopConfig>(withLang("/shop/config", lang), 60);
  } catch {
    return null;
  }
}

/** "Customers also bought": products from the same paid orders, then popular ones from the category. */
export async function getRelated(slug: string, lang?: Locale): Promise<ProductCardData[]> {
  try {
    return await get<ProductCardData[]>(withLang(`/products/${encodeURIComponent(slug)}/related`, lang), 300);
  } catch {
    return [];
  }
}
