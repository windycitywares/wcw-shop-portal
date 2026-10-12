import Link from "next/link";
import { attrKey, attrValue } from "@/i18n/attributes";
import type { Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
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
 * filtered view has a shareable URL. Values are sent as stored (English) and shown translated.
 */
export function FilterPanel({
  facets,
  searchParams,
  basePath,
  locale,
}: {
  facets: Facets;
  searchParams: SearchParams;
  basePath: string;
  locale: Locale;
}) {
  const t = getDictionary(locale);
  const groups = facets.attributes.filter((g) => !HIDDEN_KEYS.has(g.key) && g.values.length > 1);
  const q = selected(searchParams, "q")[0];
  const sort = selected(searchParams, "sort")[0];
  const hasFilters = Object.keys(searchParams).some(
    (k) => k.startsWith("attr.") || ["min_price", "max_price", "in_stock"].includes(k),
  );

  return (
    <details
      className="group rounded-[var(--radius-card)] border border-line bg-surface p-5 lg:border-0 lg:bg-transparent lg:p-0"
      open
    >
      <summary className="flex cursor-pointer list-none items-center justify-between font-medium lg:hidden [&::-webkit-details-marker]:hidden">
        {t.listing.filters}
        <span aria-hidden="true" className="text-muted group-open:rotate-45">
          +
        </span>
      </summary>
      <form action={basePath} method="get" className="mt-4 space-y-8 lg:mt-0">
        {q && <input type="hidden" name="q" value={q} />}
        {sort && <input type="hidden" name="sort" value={sort} />}

        <fieldset>
          <legend className="font-serif text-lg">{t.listing.price}</legend>
          <div className="mt-3 flex items-center gap-2">
            <label className="sr-only" htmlFor="min_price">
              {t.listing.minPrice}
            </label>
            <input
              id="min_price"
              name="min_price"
              type="number"
              min={0}
              step="1"
              inputMode="numeric"
              placeholder={facets.price_min != null ? `$${Math.floor(facets.price_min)}` : t.listing.min}
              defaultValue={selected(searchParams, "min_price")[0]}
              className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
            />
            <span aria-hidden="true" className="text-muted">
              –
            </span>
            <label className="sr-only" htmlFor="max_price">
              {t.listing.maxPrice}
            </label>
            <input
              id="max_price"
              name="max_price"
              type="number"
              min={0}
              step="1"
              inputMode="numeric"
              placeholder={facets.price_max != null ? `$${Math.ceil(facets.price_max)}` : t.listing.max}
              defaultValue={selected(searchParams, "max_price")[0]}
              className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
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
          {t.listing.inStockOnly}
        </label>

        {groups.map((group) => {
          const name = `attr.${group.key}`;
          const chosen = selected(searchParams, name);
          return (
            <fieldset key={group.key}>
              <legend className="font-serif text-lg">{attrKey(t, group.key)}</legend>
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
                      <span className="flex-1">{attrValue(t, v.value)}</span>
                      <span className="text-xs text-muted">{v.count}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
          );
        })}

        <div className="flex items-center gap-4">
          <Button type="submit" size="sm">
            {t.listing.apply}
          </Button>
          {hasFilters && (
            <Link href={q ? `${basePath}?q=${encodeURIComponent(q)}` : basePath} className="text-sm underline">
              {t.listing.clear}
            </Link>
          )}
        </div>
      </form>
    </details>
  );
}
