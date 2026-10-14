import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { attrKey, attrValue } from "@/i18n/attributes";
import { fmt, isLocale, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getProduct, getProducts, getRelated } from "@/lib/api";
import { alternates } from "@/lib/seo";
import { attributeList, displayPrice } from "@/lib/utils";
import { ProductGrid } from "@/components/catalog/ProductCard";
import { ProductGallery } from "@/components/catalog/ProductGallery";
import { PurchasePanel } from "@/components/catalog/PurchasePanel";
import { JsonLd, breadcrumbLd, productLd } from "@/components/seo/JsonLd";
import { TrackOnView } from "@/components/analytics/TrackOnView";
import { MiniCards } from "@/components/product/MiniCards";
import { RecentlyViewed } from "@/components/product/RecentlyViewed";
import { Reviews } from "@/components/product/Reviews";
import { Breadcrumbs, Container, type Crumb } from "@/components/ui/misc";
import { Stars } from "@/components/ui/Stars";

export const revalidate = 60;

type Props = { params: Promise<{ locale: string; slug: string }> };

async function load(params: Props["params"]) {
  const { locale: raw, slug } = await params;
  const locale: Locale = isLocale(raw) ? raw : "en";
  return { locale, product: await getProduct(slug, locale) };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, product } = await load(params);
  if (!product) return { title: getDictionary(locale).product.notFound };
  const description = product.seo_description || product.description?.slice(0, 160) || undefined;
  const path = `/product/${product.slug}`;
  return {
    title: product.seo_title || product.title,
    description,
    alternates: alternates(locale, path),
    openGraph: {
      title: product.title,
      description,
      url: localePath(locale, path),
      images: product.images.slice(0, 1).map((i) => ({ url: i.url, alt: i.alt || product.title })),
    },
  };
}

export default async function ProductPage({ params }: Props) {
  const { locale, product } = await load(params);
  if (!product) notFound();
  const t = getDictionary(locale);

  const crumbs: Crumb[] = [
    { label: t.nav.home, href: localePath(locale, "/") },
    ...product.breadcrumb.map((c) => ({ label: c.name, href: localePath(locale, `/category/${c.slug}`) })),
    { label: product.title },
  ];
  // Single-value attributes are product details; list values become choices in the purchase panel.
  const details = Object.entries(product.attributes).filter(
    ([, v]) => !Array.isArray(v) || v.length === 1,
  );
  const alsoBought = (await getRelated(product.slug, locale)).filter((p) => p.id !== product.id);
  const related = product.category
    ? (await getProducts({ category: product.category.slug, page_size: "5" }, locale)).items
        .filter((p) => p.id !== product.id)
        .slice(0, 4)
    : [];

  return (
    <Container className="py-8 sm:py-12">
      <Breadcrumbs items={crumbs} />
      <div className="mt-8 grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-16 xl:gap-24">
        <ProductGallery images={product.images} title={product.title} />
        <div>
          {product.category && <p className="text-sm text-muted">{product.category.name}</p>}
          <h1 className="mt-2 text-4xl sm:text-5xl">{product.title}</h1>
          {(product.rating_count ?? 0) > 0 && (
            <a href="#reviews" className="mt-3 inline-flex text-sm hover:underline">
              <Stars
                rating={product.rating_avg ?? 0}
                count={product.rating_count}
                label={fmt(t.product.rating, { rating: (product.rating_avg ?? 0).toFixed(1), count: product.rating_count ?? 0 })}
              />
            </a>
          )}
          <div className="mt-8">
            <PurchasePanel product={product} />
          </div>

          {details.length > 0 && (
            <section aria-labelledby="details-heading" className="mt-12">
              <h2 id="details-heading" className="text-2xl">
                {t.product.details}
              </h2>
              <dl className="mt-4 border-t border-line text-sm">
                {details.map(([k, v]) => (
                  <div key={k} className="grid grid-cols-[minmax(8rem,40%)_1fr] gap-4 border-b border-line py-3">
                    <dt className="text-muted">{attrKey(t, k)}</dt>
                    <dd>{attributeList(v).map((x) => attrValue(t, x)).join(", ")}</dd>
                  </div>
                ))}
                <div className="grid grid-cols-[minmax(8rem,40%)_1fr] gap-4 border-b border-line py-3">
                  <dt className="text-muted">{t.product.sku}</dt>
                  <dd>{product.sku}</dd>
                </div>
              </dl>
            </section>
          )}

          {product.description && (
            <section aria-labelledby="desc-heading" className="mt-12">
              <h2 id="desc-heading" className="text-2xl">
                {t.product.description}
              </h2>
              <div className="mt-4 max-w-[68ch] whitespace-pre-line leading-relaxed text-muted">
                {product.description}
              </div>
            </section>
          )}
        </div>
      </div>

      {related.length > 0 && (
        <section aria-labelledby="related-heading" className="mt-28 border-t border-line pt-16">
          <h2 id="related-heading" className="text-4xl">
            {t.product.related}
          </h2>
          <div className="mt-10">
            <ProductGrid products={related} locale={locale} />
          </div>
        </section>
      )}

      <TrackOnView type="product_view" productId={product.id} value={displayPrice(product).amount} />
      <Reviews slug={product.slug} />

      <MiniCards
        items={alsoBought.filter((p) => !related.some((r) => r.id === p.id))}
        title={t.discover.alsoBought}
        hrefFor={(slug) => localePath(locale, `/product/${slug}`)}
        locale={locale}
      />

      <RecentlyViewed
        current={{
          id: product.id,
          slug: product.slug,
          title: product.title,
          base_price: product.base_price,
          sale_price: product.sale_price ?? null,
          compare_at_price: displayPrice(product).compareAt,
          image: product.images[0]?.url ?? null,
        }}
      />

      <JsonLd data={productLd(product, locale)} />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </Container>
  );
}
