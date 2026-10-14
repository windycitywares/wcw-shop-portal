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
 * What to show as a product's price: the sale price with the usual price struck through while a sale is live,
 * otherwise the price (with the "compare at" price struck through if the shop set one).
 */
export function displayPrice(p: { base_price: number; compare_at_price: number | null; sale_price?: number | null }) {
  if (p.sale_price != null && p.sale_price < p.base_price) {
    return { amount: p.sale_price, compareAt: Math.max(p.base_price, p.compare_at_price ?? 0) as number | null, onSale: true };
  }
  const onSale = p.compare_at_price != null && p.compare_at_price > p.base_price;
  return { amount: p.base_price, compareAt: p.compare_at_price, onSale };
}

export const percentOff = (amount: number, compareAt: number) => Math.round((1 - amount / compareAt) * 100);

export function attributeList(value: AttributeValue): string[] {
  return Array.isArray(value) ? value.map(String) : [String(value)];
}

export function formatAttribute(value: AttributeValue): string {
  return attributeList(value).join(", ");
}

export const STOCK_LABEL: Record<string, string> = {
  in_stock: "In stock",
  out_of_stock: "Sold out",
  backorder: "Available on backorder",
  preorder: "Available for pre-order",
};

export const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  in_review: "In review",
  published: "Published",
  archived: "Archived",
};
