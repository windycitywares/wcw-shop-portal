/**
 * Server-side data access (Server Components, sitemap, metadata).
 * Storefront reads are cached and revalidated every few minutes.
 * Network failures degrade to empty results so pages still render.
 */
import "server-only";
import type { CategoryDetail, CategoryNode, Facets, Page, Product, ProductDetail } from "./types";

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

const EMPTY_PAGE: Page<Product> = { items: [], total: 0, page: 1, page_size: 24 };

export async function getCategoryTree(): Promise<CategoryNode[]> {
  try {
    return await get<CategoryNode[]>("/categories/tree");
  } catch {
    return [];
  }
}

export async function getCategory(slug: string): Promise<CategoryDetail | null> {
  try {
    return await get<CategoryDetail>(`/categories/${encodeURIComponent(slug)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function getProducts(params: URLSearchParams | Record<string, string>): Promise<Page<Product>> {
  const qs = new URLSearchParams(params).toString();
  try {
    return await get<Page<Product>>(`/products${qs ? `?${qs}` : ""}`, 60);
  } catch {
    return EMPTY_PAGE;
  }
}

export async function getProduct(slug: string): Promise<ProductDetail | null> {
  try {
    return await get<ProductDetail>(`/products/${encodeURIComponent(slug)}`, 60);
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
