import type { Crumb } from "@/components/ui/misc";
import { localePath, type Locale } from "@/i18n/config";
import { absoluteUrl, site } from "@/lib/site";
import type { ProductDetail } from "@/lib/types";

/** Renders schema.org structured data. `<` is escaped so content can't break out of the script tag. */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  );
}

export function organizationLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: site.name,
    url: site.url,
    logo: absoluteUrl("/icon.svg"),
    sameAs: site.social.map((s) => s.href),
  };
}

export function breadcrumbLd(items: Crumb[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.label,
      ...(c.href ? { item: absoluteUrl(c.href) } : {}),
    })),
  };
}

const AVAILABILITY: Record<string, string> = {
  in_stock: "https://schema.org/InStock",
  out_of_stock: "https://schema.org/OutOfStock",
  backorder: "https://schema.org/BackOrder",
  preorder: "https://schema.org/PreOrder",
};

export function productLd(p: ProductDetail, locale: Locale = "en") {
  const offer = (item: { sku: string; base_price: number; currency: string; stock_status: string }) => ({
    "@type": "Offer",
    sku: item.sku,
    price: item.base_price.toFixed(2),
    priceCurrency: item.currency,
    availability: AVAILABILITY[item.stock_status],
    url: absoluteUrl(localePath(locale, `/product/${p.slug}`)),
  });
  const brand = typeof p.attributes.Brand === "string" ? p.attributes.Brand : site.name;
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: p.title,
    sku: p.sku,
    description: p.seo_description || p.description?.slice(0, 500) || undefined,
    image: p.images.map((i) => i.url),
    brand: { "@type": "Brand", name: brand },
    category: p.category?.name,
    offers: p.variants.length
      ? {
          "@type": "AggregateOffer",
          priceCurrency: p.currency,
          lowPrice: Math.min(...p.variants.map((v) => v.base_price)).toFixed(2),
          highPrice: Math.max(...p.variants.map((v) => v.base_price)).toFixed(2),
          offerCount: p.variants.length,
          offers: p.variants.map(offer),
        }
      : offer(p),
  };
}
