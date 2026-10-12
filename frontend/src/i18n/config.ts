/**
 * Storefront languages. English lives at the bare URL (/shop), the others under a prefix
 * (/es/shop, /nl/shop). src/proxy.ts sends first-time visitors to the language their
 * browser asks for; the language switcher remembers a manual choice in a cookie.
 */
export const locales = ["en", "es", "nl"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export const localeNames: Record<Locale, string> = { en: "English", es: "Español", nl: "Nederlands" };
/** For Intl number/date formatting */
export const intlLocale: Record<Locale, string> = { en: "en-US", es: "es-US", nl: "nl-NL" };
/** For Open Graph */
export const ogLocale: Record<Locale, string> = { en: "en_US", es: "es_ES", nl: "nl_NL" };

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (locales as readonly string[]).includes(value);
}

/** "/shop" in Spanish -> "/es/shop"; English keeps the bare path. */
export function localePath(locale: Locale, path = "/"): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (locale === defaultLocale) return p;
  return p === "/" ? `/${locale}` : `/${locale}${p}`;
}

/** Strip a language prefix: "/es/shop?x=1" -> "/shop?x=1". */
export function stripLocale(path: string): string {
  const m = path.match(/^\/(es|nl|en)(?=\/|\?|$)(.*)$/);
  if (!m) return path || "/";
  return m[2] ? (m[2].startsWith("/") ? m[2] : `/${m[2]}`) : "/";
}

/** Best match from an Accept-Language header, e.g. "nl-BE,nl;q=0.9,en;q=0.8" -> "nl". */
export function matchAcceptLanguage(header: string | null | undefined): Locale {
  if (!header) return defaultLocale;
  const ranked = header
    .split(",")
    .map((part) => {
      const [tag, ...params] = part.trim().split(";");
      const q = params.find((p) => p.trim().startsWith("q="));
      return { lang: tag.trim().toLowerCase().split("-")[0], q: q ? Number(q.trim().slice(2)) || 0 : 1 };
    })
    .filter((x) => x.lang && x.q > 0)
    .sort((a, b) => b.q - a.q);
  for (const { lang } of ranked) {
    if (isLocale(lang)) return lang;
  }
  return defaultLocale;
}

/** Fill "{name}" placeholders. */
export function fmt(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
}
