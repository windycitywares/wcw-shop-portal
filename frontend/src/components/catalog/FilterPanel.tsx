import Link from "next/link";
import type { Facets } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import type { SearchParams } from "./ProductListing";

const MAX_VALUES = 12;
// Identifiers and per-product details that make poor filters
const HIDDEN_KEYS = new Set(["ASIN", "Engraving", "Size", "Closure", "Adult urn size", "Keepsake size"]);

function selected(searchParams: SearchParams, key: string): string[] {
  const v = searchParams[key];
  return Array.isArray(v) ? v : v ? [v] : [];
}

/**
 * Faceted filters as a plain GET form: works without JavaScript, and every
 * filtered view has a shareable, crawlable URL.
 */
export function FilterPanel({
  facets,
  searchParams,
  basePath,
}: {
  facets: Facets;
  searchParams: SearchParams;
  basePath: string;
}) {
  const groups = facets.attributes.filter((g) => !HIDDEN_KEYS.has(g.key) && g.values.length > 1);
  const q = selected(searchParams, "q")[0];
  const sort = selected(searchParams, "sort")[0];
  const hasFilters = Object.keys(searchParams).some(
    (k) => k.startsWith("attr.") || ["min_price", "max_price", "in_stock"].includes(k),
  );

  return (
    <details className="group rounded-[var(--radius-card)] border border-line bg-surface p-5 lg:border-0 lg:bg-transparent lg:p-0" open>
      <summary className="flex cursor-pointer list-none items-center justify-between font-medium lg:hidden">
        Filters
        <span aria-hidden="true" className="text-muted group-open:rotate-45">
          +
        </span>
      </summary>
      <form action={basePath} method="get" className="mt-4 space-y-7 lg:mt-0">
        {q && <input type="hidden" name="q" value={q} />}
        {sort && <input type="hidden" name="sort" value={sort} />}

        <fieldset>
          <legend className="text-sm font-semibold">Price</legend>
          <div className="mt-3 flex items-center gap-2">
            <label className="sr-only" htmlFor="min_price">
              Minimum price
            </label>
            <input
              id="min_price"
              name="min_price"
              type="number"
              min={0}
              step="1"
              inputMode="numeric"
              placeholder={facets.price_min != null ? `$${Math.floor(facets.price_min)}` : "Min"}
              defaultValue={selected(searchParams, "min_price")[0]}
              className="h-10 w-full rounded-lg border border-line bg-surface px-3 text-sm"
            />
            <span aria-hidden="true" className="text-muted">
              –
            </span>
            <label className="sr-only" htmlFor="max_price">
              Maximum price
            </label>
            <input
              id="max_price"
              name="max_price"
              type="number"
              min={0}
              step="1"
              inputMode="numeric"
              placeholder={facets.price_max != null ? `$${Math.ceil(facets.price_max)}` : "Max"}
              defaultValue={selected(searchParams, "max_price")[0]}
              className="h-10 w-full rounded-lg border border-line bg-surface px-3 text-sm"
            />
          </div>
        </fieldset>

        <label className="flex items-center gap-2.5 text-sm">
          <input
            type="checkbox"
            name="in_stock"
            value="true"
            defaultChecked={selected(searchParams, "in_stock")[0] === "true"}
            className="size-4 accent-[var(--color-accent)]"
          />
          In stock only
        </label>

        {groups.map((group) => {
          const name = `attr.${group.key}`;
          const chosen = selected(searchParams, name);
          return (
            <fieldset key={group.key}>
              <legend className="text-sm font-semibold">{group.key}</legend>
              <ul className="mt-3 space-y-2">
                {group.values.slice(0, MAX_VALUES).map((v) => (
                  <li key={v.value}>
                    <label className="flex items-center gap-2.5 text-sm">
                      <input
                        type="checkbox"
                        name={name}
                        value={v.value}
                        defaultChecked={chosen.includes(v.value)}
                        className="size-4 accent-[var(--color-accent)]"
                      />
                      <span className="flex-1">{v.value}</span>
                      <span className="text-xs text-muted">
                        {v.count}
                        <span className="sr-only"> products</span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
          );
        })}

        <div className="flex items-center gap-3">
          <Button type="submit" size="sm">
            Apply filters
          </Button>
          {hasFilters && (
            <Link href={q ? `${basePath}?q=${encodeURIComponent(q)}` : basePath} className="text-sm underline">
              Clear
            </Link>
          )}
        </div>
      </form>
    </details>
  );
}
