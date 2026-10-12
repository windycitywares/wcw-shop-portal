import type { Metadata } from "next";
import Link from "next/link";
import { attrValue } from "@/i18n/attributes";
import { fmt, isLocale, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getCategoryPreview, getCategoryTree, getProducts } from "@/lib/api";
import { alternates } from "@/lib/seo";
import { site } from "@/lib/site";
import type { Product } from "@/lib/types";
import { ButtonLink } from "@/components/ui/Button";
import { Container, EmptyState, Price } from "@/components/ui/misc";
import { ProductImage } from "@/components/ui/ProductImage";
import { ProductGrid } from "@/components/catalog/ProductCard";

export const revalidate = 300;

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { alternates: alternates(locale, "/") } : {};
}

/** A framed piece in the hero, with a museum-style wall label beneath. */
function HungPiece({
  product,
  locale,
  sizes,
  className,
}: {
  product: Product;
  locale: Locale;
  sizes: string;
  className?: string;
}) {
  const image = product.images[0];
  return (
    <figure className={`group relative ${className ?? ""}`}>
      <div className="mat shadow-[0_30px_60px_-30px_rgb(23_35_43/0.35)]">
        <div className="relative aspect-[4/5] overflow-hidden bg-sand">
          <ProductImage src={image?.url} alt={image?.alt || product.title} sizes={sizes} priority />
        </div>
      </div>
      <figcaption className="mt-3 pl-1">
        <Link
          href={localePath(locale, `/product/${product.slug}`)}
          className="font-serif text-[0.95rem] leading-snug after:absolute after:inset-0 group-hover:underline"
        >
          {product.title}
        </Link>
        <Price
          amount={product.base_price}
          compareAt={product.compare_at_price}
          currency={product.currency}
          locale={locale}
          className="flex text-xs text-muted sm:text-sm"
        />
      </figcaption>
    </figure>
  );
}

export default async function HomePage({ params }: Props) {
  const { locale: raw } = await params;
  const locale: Locale = isLocale(raw) ? raw : "en";
  const t = getDictionary(locale);
  const l = (p: string) => localePath(locale, p);

  const [tree, latest] = await Promise.all([
    getCategoryTree(locale),
    getProducts({ sort: "newest", page_size: "11" }, locale),
  ]);
  // With a single top-level category (e.g. "Cremation Urns"), feature its themes instead.
  const themes = tree.length === 1 ? tree[0].children : tree;
  const previews = await Promise.all(themes.map((c) => getCategoryPreview(c.slug)));
  const [first, second, third] = latest.items;
  const newest = latest.items.slice(3, 11);

  return (
    <>
      {/* Hero: the newest designs hung like framed prints */}
      <section className="overflow-hidden border-b border-line">
        <Container className="grid items-center gap-12 py-14 sm:py-20 lg:grid-cols-12 lg:gap-10 lg:py-24">
          <div className="lg:col-span-5">
            <h1 className="max-w-[14ch] text-[2.75rem] sm:text-6xl lg:text-[4.25rem]">{t.home.heroTitle}</h1>
            <p className="mt-6 max-w-md text-lg text-muted">{t.home.heroText}</p>
            <div className="mt-9 flex flex-wrap gap-3">
              <ButtonLink href={l("/shop")} size="lg">
                {t.home.shopUrns}
              </ButtonLink>
              <ButtonLink href="#themes" variant="secondary" size="lg">
                {t.home.browseThemes}
              </ButtonLink>
            </div>
          </div>
          {first && (
            // One entrance for the whole hang (the page's single orchestrated motion)
            <div className="hang grid grid-cols-2 items-start gap-4 sm:grid-cols-3 sm:gap-5 lg:col-span-7 lg:pl-4">
              <HungPiece product={first} locale={locale} sizes="(min-width: 1024px) 20vw, (min-width: 640px) 30vw, 46vw" />
              {second && (
                <HungPiece
                  product={second}
                  locale={locale}
                  sizes="(min-width: 1024px) 20vw, (min-width: 640px) 30vw, 46vw"
                  className="mt-12 sm:mt-20"
                />
              )}
              {third && (
                <HungPiece product={third} locale={locale} sizes="(min-width: 1024px) 20vw, 30vw" className="hidden sm:mt-8 sm:block" />
              )}
            </div>
          )}
        </Container>
      </section>

      {/* Themes */}
      {themes.length > 0 && (
        <section id="themes" aria-labelledby="themes-heading" className="scroll-mt-24">
          <Container className="py-20 sm:py-24">
            <div className="max-w-2xl">
              <h2 id="themes-heading" className="text-4xl sm:text-5xl">
                {t.home.themesTitle}
              </h2>
              <p className="mt-4 text-lg text-muted">{t.home.themesText}</p>
            </div>
            <ul className="mt-12 grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 sm:gap-x-6 lg:grid-cols-5">
              {themes.map((c, i) => {
                const preview = previews[i];
                return (
                  <li key={c.id} className="group relative">
                    <div className="mat transition-colors duration-300 group-hover:border-ink/30">
                      <div className="relative aspect-square overflow-hidden bg-sand">
                        <ProductImage
                          src={preview.image}
                          alt=""
                          sizes="(min-width: 1024px) 18vw, (min-width: 640px) 30vw, 46vw"
                          className="transition-transform duration-700 ease-out group-hover:scale-[1.03]"
                        />
                      </div>
                    </div>
                    <Link
                      href={l(`/category/${c.slug}`)}
                      className="mt-3 block font-serif text-lg leading-snug after:absolute after:inset-0"
                    >
                      {c.name}
                    </Link>
                    <p className="text-sm text-muted">
                      {preview.total === 1 ? t.home.oneDesign : fmt(t.home.designs, { count: preview.total })}
                    </p>
                  </li>
                );
              })}
            </ul>
          </Container>
        </section>
      )}

      {/* How sizes work */}
      <section aria-labelledby="sizes-heading" className="border-y border-line bg-surface">
        <Container className="grid gap-10 py-20 sm:py-24 lg:grid-cols-[1fr_1.35fr] lg:gap-20">
          <div>
            <h2 id="sizes-heading" className="text-4xl sm:text-5xl">
              {t.home.sizesTitle}
            </h2>
            <p className="mt-4 max-w-md text-lg text-muted">{t.home.sizesText}</p>
          </div>
          <dl className="border-t border-line">
            {t.home.sizes.map((s) => (
              <div key={s.name} className="grid gap-1 border-b border-line py-4 sm:grid-cols-[16rem_1fr] sm:gap-6">
                <dt className="font-serif text-lg">{attrValue(t, s.name)}</dt>
                <dd className="text-muted">{s.text}</dd>
              </div>
            ))}
          </dl>
        </Container>
      </section>

      {/* Newest */}
      <section aria-labelledby="new-heading">
        <Container className="py-20 sm:py-24">
          <div className="flex items-end justify-between gap-4">
            <h2 id="new-heading" className="text-4xl sm:text-5xl">
              {t.home.newTitle}
            </h2>
            <Link href={l("/shop?sort=newest")} className="text-sm font-medium text-accent underline underline-offset-4">
              {t.home.viewAll}
            </Link>
          </div>
          <div className="mt-12">
            {newest.length ? (
              <ProductGrid products={newest} locale={locale} />
            ) : (
              <EmptyState title={t.home.emptyTitle}>{t.home.emptyText}</EmptyState>
            )}
          </div>
        </Container>
      </section>

      {/* Materials */}
      <section aria-labelledby="craft-heading">
        <Container className="pb-20 sm:pb-24">
          <h2 id="craft-heading" className="text-4xl sm:text-5xl">
            {t.home.craftTitle}
          </h2>
          <ul className="mt-10 grid gap-10 sm:grid-cols-3 sm:gap-8">
            {t.home.craft.map((c) => (
              <li key={c.title} className="border-t border-ink pt-5">
                <h3 className="text-xl">{c.title}</h3>
                <p className="mt-2 text-muted">{c.text}</p>
              </li>
            ))}
          </ul>
        </Container>
      </section>

      {/* Etsy */}
      <section aria-labelledby="etsy-heading">
        <Container>
          <div className="flex flex-col items-start justify-between gap-6 rounded-[var(--radius-card)] border border-line bg-surface px-6 py-10 sm:flex-row sm:items-center sm:px-10">
            <div>
              <h2 id="etsy-heading" className="text-3xl">
                {t.home.etsyTitle}
              </h2>
              <p className="mt-2 text-muted">{t.home.etsyText}</p>
            </div>
            <a
              href={site.social[0].href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-11 shrink-0 items-center rounded-[var(--radius-control)] border border-ink/25 px-6 text-sm font-medium hover:border-ink hover:bg-canvas"
            >
              {t.home.etsyCta}
              <span className="sr-only"> {t.footer.newTab}</span>
            </a>
          </div>
        </Container>
      </section>
    </>
  );
}
