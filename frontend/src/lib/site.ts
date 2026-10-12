/** Brand + site settings. Change here, not in components. */
export const site = {
  name: "Windy City Wares",
  shortName: "WCW",
  tagline: "Memorial urns and keepsakes to honor the ones you love.",
  description:
    "Windy City Wares — cremation urns and matching keepsakes with artwork chosen to honor a loved one.",
  url: (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, ""),
  locale: "en_US",
  currency: "USD",
  social: [{ label: "Etsy", href: "https://www.etsy.com/shop/WindyCityWaresUS" }],
  /**
   * Search engines may index the site only when NEXT_PUBLIC_ALLOW_INDEXING=true.
   * Off by default so the shop.windycitywares.com build-out stays out of Google
   * until it moves to the main domain.
   */
  allowIndexing: process.env.NEXT_PUBLIC_ALLOW_INDEXING === "true",
} as const;

export function absoluteUrl(path = "/"): string {
  return `${site.url}${path.startsWith("/") ? path : `/${path}`}`;
}
