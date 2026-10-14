import type { Coupon, CouponKind, CouponStatus, Sale } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import type { Tone } from "@/components/admin/ui/Pill";

export const COUPON_STATUS_LABEL: Record<CouponStatus, string> = {
  active: "Active",
  scheduled: "Not started",
  expired: "Expired",
  used_up: "Used up",
  paused: "Paused",
};
export const COUPON_STATUS_TONE: Record<CouponStatus, Tone> = {
  active: "success",
  scheduled: "info",
  expired: "neutral",
  used_up: "neutral",
  paused: "warning",
};
export const SALE_STATUS_LABEL: Record<Sale["status"], string> = { live: "Live now", scheduled: "Scheduled", ended: "Ended", paused: "Paused" };
export const SALE_STATUS_TONE: Record<Sale["status"], Tone> = { live: "success", scheduled: "info", ended: "neutral", paused: "warning" };

export const SOURCE_LABEL: Record<Coupon["source"], string> = {
  manual: "Made by hand",
  generated: "Batch",
  welcome: "Welcome code",
  personal: "Personal code",
};

/** "10% off", "$5.00 off", "Free shipping". */
export function describeDiscount(kind: CouponKind | "percent" | "fixed", value: number): string {
  if (kind === "free_shipping") return "Free shipping";
  return kind === "percent" ? `${value}% off` : `${formatPrice(value, "USD")} off`;
}

/** The conditions of a coupon as short phrases. */
export function describeRules(c: Coupon, categoryName: (id: number) => string | null): string[] {
  const out: string[] = [];
  if (c.min_subtotal != null) out.push(`Spend ${formatPrice(c.min_subtotal, "USD")}+`);
  if (c.max_discount != null) out.push(`Up to ${formatPrice(c.max_discount, "USD")} off`);
  if (c.scope === "category") out.push(c.category_id != null ? (categoryName(c.category_id) ?? "One category") : "One category");
  if (c.scope === "products") out.push(`${c.product_ids.length} chosen ${c.product_ids.length === 1 ? "product" : "products"}`);
  if (c.exclude_sale_items) out.push("Not on sale items");
  if (c.first_order_only) out.push("First order only");
  if (c.per_customer_limit != null) out.push(`${c.per_customer_limit}× per customer`);
  return out;
}

const DAY = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" });
export const day = (iso: string | null) => (iso ? DAY.format(new Date(iso)) : "—");

/** The body for saving a coupon again with one thing changed (the API replaces the whole coupon). */
export function couponUpdateBody(c: Coupon, changes: Partial<{ is_active: boolean }> = {}) {
  return {
    scope: c.scope,
    category_id: c.category_id,
    product_ids: c.product_ids,
    description: c.description,
    kind: c.kind,
    value: c.value,
    min_subtotal: c.min_subtotal,
    max_discount: c.max_discount,
    exclude_sale_items: c.exclude_sale_items,
    first_order_only: c.first_order_only,
    per_customer_limit: c.per_customer_limit,
    starts_at: c.starts_at,
    expires_at: c.expires_at,
    usage_limit: c.usage_limit,
    is_active: c.is_active,
    ...changes,
  };
}

export function saleBody(s: Sale, changes: Partial<{ is_active: boolean }> = {}) {
  return {
    name: s.name,
    label: s.label,
    kind: s.kind,
    value: s.value,
    scope: s.scope,
    category_id: s.category_id,
    product_ids: s.product_ids,
    starts_at: s.starts_at,
    ends_at: s.ends_at,
    is_active: s.is_active,
    ...changes,
  };
}

/** A hard-to-confuse random code (no 0/O or 1/I). */
export function randomCode(length = 8): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join("");
}
