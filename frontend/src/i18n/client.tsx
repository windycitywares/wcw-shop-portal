"use client";

import { createContext, useContext, useMemo } from "react";
import { fmt, localePath, type Locale } from "./config";
import type { Dictionary } from "./dictionaries";
import { getDictionary } from "./dictionaries";

interface I18n {
  locale: Locale;
  t: Dictionary;
  /** Localized link: href("/shop") -> "/es/shop" in Spanish */
  href: (path: string) => string;
  fmt: typeof fmt;
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const value = useMemo<I18n>(
    () => ({ locale, t: getDictionary(locale), href: (p) => localePath(locale, p), fmt }),
    [locale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}

/** For components that also render outside the storefront (e.g. admin): English fallback. */
export function useOptionalI18n(): I18n {
  const ctx = useContext(I18nContext);
  return ctx ?? { locale: "en", t: getDictionary("en"), href: (p) => p, fmt };
}
