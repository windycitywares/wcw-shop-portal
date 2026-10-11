/** Brand + site settings. Change here, not in components. */
export const site = {
  name: "Windy City Wares",
  shortName: "WCW",
  tagline: "Thoughtfully made goods, inspired by the Windy City.",
  description:
    "Windy City Wares — home decor, kitchen goods and gifts. Shop our collection online.",
  url: (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, ""),
  locale: "en_US",
  currency: "USD",
  social: [{ label: "Etsy", href: "https://www.etsy.com/shop/WindyCityWaresUS" }],
} as const;

export function absoluteUrl(path = "/"): string {
  return `${site.url}${path.startsWith("/") ? path : `/${path}`}`;
}
