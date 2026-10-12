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
