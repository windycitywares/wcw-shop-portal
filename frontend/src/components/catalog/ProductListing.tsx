import Link from "next/link";
import { Suspense } from "react";
import { defaultLocale, fmt, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getFacets, getProducts } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Breadcrumbs, Container, EmptyState, type Crumb } from "@/components/ui/misc";
import { TrackOnView } from "@/components/analytics/TrackOnView";
import { FilterPanel } from "./FilterPanel";
import { InfiniteProducts } from "./InfiniteProducts";
import { SortSelect } from "./SortSelect";
import { PageSizeSelect } from "./PageSizeSelect";
import { PAGE_SIZES, DEFAULT_PAGE_SIZE } from "./pageSizes";
import { Pager } from "./Pager";

export type SearchParams = Record<string, string | string[] | undefined>;

const PASSTHROUGH = ["q", "min_price", "max_price", "in_stock", "on_sale", "min_rating", "sort", "page"];

/** How many products per page: the visitor's pick if it is one of the offered sizes, else the default. */
function pageSizeOf(searchParams: SearchParams): number {
  const raw = Array.isArray(searchParams.page_size) ? searchParams.page_size[0] : searchParams.page_size;
  const n = Number(raw);
  return (PAGE_SIZES as readonly number[]).includes(n) ? n : DEFAULT_PAGE_SIZE;
}

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
  params.set("page_size", String(pageSizeOf(searchParams)));
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
  const apiParams = toApiParams(searchParams, categorySlug, fixedParams);
  apiParams.delete("page");
  if (locale !== defaultLocale) apiParams.set("lang", locale);
  const apiQuery = apiParams.toString();
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
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <Suspense fallback={null}>
                <PageSizeSelect value={pageSizeOf(searchParams)} />
                <SortSelect />
              </Suspense>
            </div>
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
            <InfiniteProducts
              key={apiQuery}
              initial={result.items}
              total={result.total}
              startPage={page}
              pageSize={result.page_size}
              query={apiQuery}
              priorityCount={3}
            />
          )}
          {/* Without JavaScript (and for crawlers) the numbered pages remain. */}
          {pages > 1 && (
            <noscript>
              <Pager page={page} pages={pages} href={(n) => pageHref(searchParams, n, basePath)} t={t} />
            </noscript>
          )}
        </section>
      </div>
    </Container>
  );
}
