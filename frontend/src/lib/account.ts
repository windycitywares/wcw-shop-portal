"use client";

import { apiFetch } from "./client-api";

export interface Address {
  id: number;
  label: string | null;
  full_name: string;
  company: string | null;
  line1: string;
  line2: string | null;
  city: string;
  region: string | null;
  postal_code: string;
  country: string;
  phone: string | null;
  is_default: boolean;
}

export type AddressInput = Omit<Address, "id">;

export const addressesApi = {
  list: () => apiFetch<Address[]>("/account/addresses"),
  create: (a: AddressInput) => apiFetch<Address>("/account/addresses", { method: "POST", body: JSON.stringify(a) }),
  update: (id: number, a: AddressInput) =>
    apiFetch<Address>(`/account/addresses/${id}`, { method: "PUT", body: JSON.stringify(a) }),
  makeDefault: (id: number) => apiFetch<Address>(`/account/addresses/${id}/default`, { method: "POST" }),
  remove: (id: number) => apiFetch<void>(`/account/addresses/${id}`, { method: "DELETE" }),
};

export const passwordApi = {
  forgot: (email: string, locale: string) =>
    apiFetch<{ detail: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email, locale }) }),
  reset: (token: string, new_password: string) =>
    apiFetch<{ detail: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password }) }),
};

export interface ContactInput {
  name: string;
  email: string;
  subject: string;
  message: string;
  order_number: string | null;
  locale: string;
  captcha_token: string | null;
  website: string;
}

export const sendContact = (c: ContactInput) =>
  apiFetch<{ detail: string }>("/contact", { method: "POST", body: JSON.stringify(c) });

/** Countries offered in the address form (ISO codes). US first; extend as shipping expands. */
export const COUNTRIES = ["US", "CA", "MX", "GB", "IE", "NL", "BE", "DE", "FR", "ES", "IT", "AU", "NZ", "IN"] as const;

export function countryName(code: string, locale: string) {
  try {
    return new Intl.DisplayNames([locale], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}
