import type { MetadataRoute } from "next";
import { absoluteUrl, site } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  if (!site.allowIndexing) {
    // Pre-launch (e.g. shop.windycitywares.com): keep the whole site out of search engines.
    return { rules: [{ userAgent: "*", disallow: "/" }] };
  }
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: [
          "/admin", "/account", "/cart", "/checkout", "/login", "/search", "/order/", "/track-order", "/unsubscribe",
          "/*/account", "/*/cart", "/*/checkout", "/*/order/", "/*/unsubscribe",
        ] }],
    sitemap: absoluteUrl("/sitemap.xml"),
  };
}
