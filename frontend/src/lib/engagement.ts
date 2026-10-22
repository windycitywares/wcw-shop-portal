"use client";

import { apiFetch } from "./client-api";
import type { ProductCardData } from "./types";

export type { ProductCardData };

/** Reviews, wishlist, back-in-stock and recently viewed (shopper side). */

export interface Review {
  id: number;
  author_name: string;
  rating: number;
  title: string | null;
  body: string;
  verified: boolean;
  helpful_count: number;
  created_at: string;
  reply: string | null;
  replied_at: string | null;
  helpful_by_me: boolean;
}

export interface ReviewPage {
  summary: { average: number; count: number; distribution: Record<string, number> };
  items: Review[];
  total: number;
  page: number;
  page_size: number;
  can_review: boolean;
  purchased: boolean;
  reviewed: boolean;
}

export type ReviewSort = "helpful" | "newest" | "highest" | "lowest";


export const reviewsApi = {
  list: (slug: string, sort: ReviewSort, page: number) =>
    apiFetch<ReviewPage>(`/products/${encodeURIComponent(slug)}/reviews?sort=${sort}&page=${page}&page_size=5`),
  submit: (slug: string, body: { rating: number; title: string | null; body: string; locale: string }) =>
    apiFetch<{ status: "pending" | "approved"; review: Review }>(`/products/${encodeURIComponent(slug)}/reviews`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  helpful: (id: number) => apiFetch<Review>(`/reviews/${id}/helpful`, { method: "POST" }),
};

// One request per page view for the hearts on every card, shared by all of them.
let wishlistIds: Promise<Set<number>> | null = null;

export const wishlistApi = {
  ids(): Promise<Set<number>> {
    wishlistIds ??= apiFetch<number[]>("/account/wishlist/ids")
      .then((ids) => new Set(ids))
      .catch(() => {
        wishlistIds = null;
        return new Set<number>();
      });
    return wishlistIds;
  },
  async add(id: number) {
    await apiFetch(`/account/wishlist/${id}`, { method: "PUT" });
    (await wishlistApi.ids()).add(id);
  },
  async remove(id: number) {
    await apiFetch(`/account/wishlist/${id}`, { method: "DELETE" });
    (await wishlistApi.ids()).delete(id);
  },
  list: (lang: string) => apiFetch<ProductCardData[]>(`/account/wishlist?lang=${lang}`),
  forget() {
    wishlistIds = null; // after signing in or out
  },
};

export interface StockRequest {
  id: number;
  product_id: number;
  title: string;
  slug: string;
  image: string | null;
  options: Record<string, string>;
  note: string | null;
  kind: "restock" | "request";
  status: "waiting" | "notified" | "closed";
  created_at: string;
  notified_at: string | null;
}

/** Signed-in customers ask to be emailed about a combination (or request one the shop doesn't sell yet). */
export const stockRequests = {
  create: (productId: number, options: Record<string, string>, note: string, locale: string) =>
    apiFetch<{ kind: "restock" | "request"; options: Record<string, string>; already: boolean }>(`/products/${productId}/stock-requests`, {
      method: "POST",
      body: JSON.stringify({ options, note: note.trim() || null, locale }),
    }),
  mine: () => apiFetch<StockRequest[]>("/account/stock-requests"),
  cancel: (id: number) => apiFetch(`/account/stock-requests/${id}`, { method: "DELETE" }),
};

/** Recently viewed designs, kept only in this browser (never sent anywhere). */
const RECENT_KEY = "wcw-recent";
const RECENT_MAX = 8;

export const recentlyViewed = {
  read(): ProductCardData[] {
    try {
      const raw = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      return Array.isArray(raw) ? raw.slice(0, RECENT_MAX) : [];
    } catch {
      return [];
    }
  },
  remember(p: ProductCardData) {
    try {
      const next = [p, ...recentlyViewed.read().filter((x) => x.id !== p.id)].slice(0, RECENT_MAX);
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable */
    }
  },
};
