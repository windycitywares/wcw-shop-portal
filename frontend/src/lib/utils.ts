import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { intlLocale, type Locale } from "@/i18n/config";
import type { AttributeValue } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(amount: number, currency = "USD", locale: Locale = "en") {
  return new Intl.NumberFormat(intlLocale[locale], { style: "currency", currency }).format(amount);
}

/**
 * What the shopper pays now and the crossed-out price beside it: a running sale wins over the
 * stored "compare at" price (the API sets sale_price while a sale is on).
 */
export function displayPrice(p: { base_price: number; compare_at_price: number | null; sale_price?: number | null }) {
  if (p.sale_price != null && p.sale_price < p.base_price) return { amount: p.sale_price, compareAt: p.base_price };
  return { amount: p.base_price, compareAt: p.compare_at_price };
}

/** Whole-number percentage saved, or 0. */
export function percentOff(amount: number, compareAt: number | null | undefined) {
  return compareAt && compareAt > amount ? Math.round((1 - amount / compareAt) * 100) : 0;
}

export function attributeList(value: AttributeValue): string[] {
  return Array.isArray(value) ? value.map(String) : [String(value)];
}

export function formatAttribute(value: AttributeValue): string {
  return attributeList(value).join(", ");
}

export const STOCK_LABEL: Record<string, string> = {
  in_stock: "In stock",
  out_of_stock: "Out of stock",
  backorder: "Available on backorder",
  preorder: "Available for pre-order",
};

export const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  in_review: "In review",
  published: "Published",
  archived: "Archived",
};
