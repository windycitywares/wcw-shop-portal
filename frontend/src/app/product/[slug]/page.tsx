import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getProduct, getProducts } from "@/lib/api";
import { formatAttribute } from "@/lib/utils";
import { ProductGrid } from "@/components/catalog/ProductCard";
import { ProductGallery } from "@/components/catalog/ProductGallery";
import { PurchasePanel } from "@/components/catalog/PurchasePanel";
import { JsonLd, breadcrumbLd, productLd } from "@/components/seo/JsonLd";
import { Breadcrumbs, Container, type Crumb } from "@/components/ui/misc";

export const revalidate = 60;

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) return { title: "Product not found" };
  const description = product.seo_description || product.description?.slice(0, 160) || undefined;
  return {
    title: product.seo_title || product.title,
    description,
    alternates: { canonical: `/product/${product.slug}` },
    openGraph: {
      title: product.title,
      description,
      url: `/product/${product.slug}`,
      images: product.images.slice(0, 1).map((i) => ({ url: i.url, alt: i.alt || product.title })),
    },
  };
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();

  const crumbs: Crumb[] = [
    { label: "Home", href: "/" },
    ...product.breadcrumb.map((c) => ({ label: c.name, href: `/category/${c.slug}` })),
    { label: product.title },
  ];
  // Single-value attributes are product details; list values become choices in the purchase panel.
  const details = Object.entries(product.attributes).filter(
    ([, v]) => !Array.isArray(v) || v.length === 1 || product.variants.length > 0,
  );
  const related = product.category
    ? (await getProducts({ category: product.category.slug, page_size: "5" })).items
        .filter((p) => p.id !== product.id)
        .slice(0, 4)
    : [];

  return (
    <Container className="py-10">
      <Breadcrumbs items={crumbs} />
      <div className="mt-6 grid gap-10 lg:grid-cols-2 lg:gap-16">
        <ProductGallery images={product.images} title={product.title} />
        <div>
          <h1 className="text-4xl leading-tight sm:text-5xl">{product.title}</h1>
          <div className="mt-6">
            <PurchasePanel product={product} />
          </div>
          {product.description && (
            <section aria-labelledby="desc-heading" className="mt-10 border-t border-line pt-8">
              <h2 id="desc-heading" className="text-xl">
                Description
              </h2>
              <div className="mt-3 whitespace-pre-line leading-relaxed text-muted">{product.description}</div>
            </section>
          )}
          {details.length > 0 && (
            <section aria-labelledby="details-heading" className="mt-8 border-t border-line pt-8">
              <h2 id="details-heading" className="text-xl">
                Details
              </h2>
              <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-8 gap-y-2 text-sm">
                {details.map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="text-muted">{k}</dt>
                    <dd>{formatAttribute(v)}</dd>
                  </div>
                ))}
                <div className="contents">
                  <dt className="text-muted">SKU</dt>
                  <dd>{product.sku}</dd>
                </div>
              </dl>
            </section>
          )}
        </div>
      </div>

      {related.length > 0 && (
        <section aria-labelledby="related-heading" className="mt-24">
          <h2 id="related-heading" className="text-3xl">
            You may also like
          </h2>
          <div className="mt-8">
            <ProductGrid products={related} />
          </div>
        </section>
      )}

      <JsonLd data={productLd(product)} />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </Container>
  );
}
