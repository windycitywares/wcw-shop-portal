import Link from "next/link";
import { Suspense } from "react";
import { getFacets, getProducts } from "@/lib/api";
import { Breadcrumbs, Container, EmptyState, type Crumb } from "@/components/ui/misc";
import { FilterPanel } from "./FilterPanel";
import { ProductGrid } from "./ProductCard";
import { SortSelect } from "./SortSelect";

export type SearchParams = Record<string, string | string[] | undefined>;

const PAGE_SIZE = 24;
const PASSTHROUGH = ["q", "min_price", "max_price", "in_stock", "sort", "page"];

/** Converts Next's searchParams into the API's query string. */
function toApiParams(searchParams: SearchParams, category?: string): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, raw] of Object.entries(searchParams)) {
    const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
    if (PASSTHROUGH.includes(key) || key.startsWith("attr.")) {
      values.filter(Boolean).forEach((v) => params.append(key, v));
    }
  }
  if (category) params.set("category", category);
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
  title,
  description,
  breadcrumb,
  searchParams,
  basePath,
  categorySlug,
  subcategories,
}: {
  title: string;
  description?: string | null;
  breadcrumb?: Crumb[];
  searchParams: SearchParams;
  basePath: string;
  categorySlug?: string;
  subcategories?: { name: string; slug: string }[];
}) {
  const [result, facets] = await Promise.all([
    getProducts(toApiParams(searchParams, categorySlug)),
    getFacets(categorySlug),
  ]);
  const page = result.page;
  const pages = Math.max(1, Math.ceil(result.total / result.page_size));

  return (
    <Container className="py-10">
      {breadcrumb && <Breadcrumbs items={breadcrumb} />}
      <div className="mt-4 max-w-2xl">
        <h1 className="text-4xl sm:text-5xl">{title}</h1>
        {description && <p className="mt-3 text-muted">{description}</p>}
      </div>

      {subcategories && subcategories.length > 0 && (
        <nav aria-label="Sub-categories" className="mt-6">
          <ul className="flex flex-wrap gap-2">
            {subcategories.map((c) => (
              <li key={c.slug}>
                <Link
                  href={`/category/${c.slug}`}
                  className="inline-block rounded-full border border-line bg-surface px-4 py-1.5 text-sm hover:border-ink/40"
                >
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <div className="mt-8 grid gap-10 lg:grid-cols-[16rem_1fr]">
        <aside aria-label="Filters">
          <FilterPanel facets={facets} searchParams={searchParams} basePath={basePath} />
        </aside>
        <section aria-labelledby="results-heading">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h2 id="results-heading" className="font-sans text-sm text-muted" aria-live="polite">
              {result.total} {result.total === 1 ? "product" : "products"}
            </h2>
            <Suspense fallback={null}>
              <SortSelect />
            </Suspense>
          </div>
          {result.items.length === 0 ? (
            <EmptyState title="Nothing here yet">
              Try removing a filter, or <Link href="/shop" className="underline">browse everything</Link>.
            </EmptyState>
          ) : (
            <ProductGrid products={result.items} priorityCount={4} />
          )}
          {pages > 1 && (
            <nav aria-label="Pagination" className="mt-12 flex items-center justify-center gap-2 text-sm">
              {page > 1 && (
                <Link href={pageHref(searchParams, page - 1, basePath)} rel="prev" className="rounded-full border border-line px-4 py-2 hover:border-ink/40">
                  Previous
                </Link>
              )}
              <span className="px-3 text-muted">
                Page {page} of {pages}
              </span>
              {page < pages && (
                <Link href={pageHref(searchParams, page + 1, basePath)} rel="next" className="rounded-full border border-line px-4 py-2 hover:border-ink/40">
                  Next
                </Link>
              )}
            </nav>
          )}
        </section>
      </div>
    </Container>
  );
}
