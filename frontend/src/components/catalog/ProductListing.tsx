import Link from "next/link";
import { Suspense } from "react";
import { fmt, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getFacets, getProducts } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Breadcrumbs, Container, EmptyState, type Crumb } from "@/components/ui/misc";
import { TrackOnView } from "@/components/analytics/TrackOnView";
import { FilterPanel } from "./FilterPanel";
import { ProductGrid } from "./ProductCard";
import { SortSelect } from "./SortSelect";

export type SearchParams = Record<string, string | string[] | undefined>;

const PAGE_SIZE = 24;
const PASSTHROUGH = ["q", "min_price", "max_price", "in_stock", "on_sale", "min_rating", "sort", "page"];

/** Converts Next's searchParams into the API's query string. */
function toApiParams(searchParams: SearchParams, category?: string, fixed?: Record<string, string>): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, raw] of Object.entries(searchParams)) {
    const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
    if (PASSTHROUGH.includes(key) || key.startsWith("attr.")) {
      values.filter(Boolean).forEach((v) => params.append(key, v));
    }
  }
  if (category) params.set("category", category);
  for (const [key, value] of Object.entries(fixed ?? {})) params.set(key, value);
  params.set("page_size", String(PAGE_SIZE));
  return params;
}

function pageHref(searchParams: SearchParams, page: number, basePath: string) {
  const params = new URLSearchParams();
  for (const [key, raw] of Object.entries(searchParams)) {
    (Array.isArray(raw) ? raw : raw ? [raw] : []).forEach((v) => params.append(key, v));
  }
  params.set("page", String(page));
  return `${basePath}?${params.toString()}`;
}

export async function ProductListing({
  locale,
  title,
  description,
  breadcrumb,
  searchParams,
  path,
  categorySlug,
  subcategories,
  currentSlug,
  fixedParams,
  emptyState,
  searchTerm,
}: {
  locale: Locale;
  title: string;
  description?: string | null;
  breadcrumb?: Crumb[];
  searchParams: SearchParams;
  /** Unlocalized path of this listing, e.g. "/shop" */
  path: string;
  categorySlug?: string;
  /** Sibling or child categories shown as a theme strip */
  subcategories?: { name: string; slug: string }[];
  currentSlug?: string;
  /** Filters this page always applies, e.g. { on_sale: "true" } for Deals */
  fixedParams?: Record<string, string>;
  /** Shown instead of the grid when nothing matches and no filter was chosen */
  emptyState?: React.ReactNode;
  /** Set on the search page: records the search and how many results it found (with consent) */
  searchTerm?: string;
}) {
  const t = getDictionary(locale);
  const basePath = localePath(locale, path);
  const [result, facets] = await Promise.all([
    getProducts(toApiParams(searchParams, categorySlug, fixedParams), locale),
    getFacets(categorySlug),
  ]);
  const page = result.page;
  const pages = Math.max(1, Math.ceil(result.total / result.page_size));

  return (
    <Container className="py-10 sm:py-14">
      {breadcrumb && <Breadcrumbs items={breadcrumb} />}
      {searchTerm && result.page === 1 && <TrackOnView type="search" q={searchTerm} results={result.total} />}
      <div className="mt-6 max-w-3xl">
        <h1 className="text-[2.75rem] sm:text-6xl">{title}</h1>
        {description && <p className="mt-4 max-w-2xl text-lg text-muted">{description}</p>}
      </div>

      {subcategories && subcategories.length > 0 && (
        <nav aria-label={t.listing.subcategories} className="-mx-4 mt-8 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <ul className="flex w-max gap-2 sm:w-auto sm:flex-wrap">
            {subcategories.map((c) => (
              <li key={c.slug}>
                <Link
                  href={localePath(locale, `/category/${c.slug}`)}
                  aria-current={c.slug === currentSlug ? "page" : undefined}
                  className={cn(
                    "inline-block whitespace-nowrap rounded-full border px-4 py-1.5 text-sm",
                    c.slug === currentSlug
                      ? "border-ink bg-ink text-canvas"
                      : "border-line bg-surface hover:border-ink/40",
                  )}
                >
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <div className="mt-10 grid gap-10 border-t border-line pt-8 lg:grid-cols-[15rem_1fr] lg:gap-14">
        <aside aria-label={t.listing.filters}>
          <FilterPanel facets={facets} searchParams={searchParams} basePath={basePath} locale={locale} />
        </aside>
        <section aria-labelledby="results-heading">
          <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
            <h2 id="results-heading" className="font-sans text-sm font-normal text-muted" aria-live="polite">
              {result.total === 1 ? t.listing.productOne : fmt(t.listing.productOther, { count: result.total })}
            </h2>
            <Suspense fallback={null}>
              <SortSelect />
            </Suspense>
          </div>
          {result.items.length === 0 && emptyState && result.page === 1 ? (
            emptyState
          ) : result.items.length === 0 ? (
            <EmptyState title={t.listing.emptyTitle}>
              {t.listing.emptyBefore}{" "}
              <Link href={localePath(locale, "/shop")} className="underline">
                {t.listing.emptyLink}
              </Link>
              .
            </EmptyState>
          ) : (
            <ProductGrid products={result.items} locale={locale} priorityCount={3} columns={3} />
          )}
          {pages > 1 && (
            <nav aria-label={t.listing.pagination} className="mt-16 flex items-center justify-center gap-2 text-sm">
              {page > 1 && (
                <Link
                  href={pageHref(searchParams, page - 1, basePath)}
                  rel="prev"
                  className="rounded-[var(--radius-control)] border border-line bg-surface px-4 py-2 hover:border-ink/40"
                >
                  {t.listing.previous}
                </Link>
              )}
              <span className="px-3 text-muted">{fmt(t.listing.pageOf, { page, pages })}</span>
              {page < pages && (
                <Link
                  href={pageHref(searchParams, page + 1, basePath)}
                  rel="next"
                  className="rounded-[var(--radius-control)] border border-line bg-surface px-4 py-2 hover:border-ink/40"
                >
                  {t.listing.next}
                </Link>
              )}
            </nav>
          )}
        </section>
      </div>
    </Container>
  );
}
