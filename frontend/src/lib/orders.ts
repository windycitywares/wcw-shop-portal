"use client";

import { apiFetch } from "./client-api";
import type { PaymentAction, PublicOrder } from "./types";

/** Shopper-side order calls. Private links are never cached (the API sends no-store). */
export const ordersApi = {
  byToken: (token: string, lang: string) =>
    apiFetch<PublicOrder>(`/orders/by-token/${encodeURIComponent(token)}?lang=${lang}`),
  confirm: (token: string, sessionId: string | null, lang: string) =>
    apiFetch<PublicOrder>(`/orders/by-token/${encodeURIComponent(token)}/confirm?lang=${lang}`, {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),
  pay: (token: string, lang: string) =>
    apiFetch<PaymentAction>(`/orders/by-token/${encodeURIComponent(token)}/pay?lang=${lang}`, { method: "POST" }),
};

/** One id per checkout attempt, so a double click or a retry can never create two orders. */
export function newIdempotencyKey(): string {
  try {
    return `co-${crypto.randomUUID()}`;
  } catch {
    return `co-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  }
}
