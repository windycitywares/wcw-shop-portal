import type { Metadata } from "next";
import { localePath, locales, type Locale } from "@/i18n/config";

/** canonical + hreflang links for a page that exists in every language. */
export function alternates(locale: Locale, path: string): Metadata["alternates"] {
  return {
    canonical: localePath(locale, path),
    languages: {
      ...Object.fromEntries(locales.map((l) => [l, localePath(l, path)])),
      "x-default": localePath("en", path),
    },
  };
}
