import Link from "next/link";
import type { ProductCardData } from "@/lib/types";
import { displayPrice, formatPrice } from "@/lib/utils";
import { ProductImage } from "@/components/ui/ProductImage";

/** A compact row of products (recently viewed, also bought). Works in server and client components. */
export function MiniCards({
  items,
  title,
  hrefFor,
  locale,
  limit = 4,
}: {
  items: ProductCardData[];
  title: string;
  hrefFor: (slug: string) => string;
  locale: "en" | "es" | "nl";
  limit?: number;
}) {
  if (!items.length) return null;
  return (
    <section aria-label={title} className="mt-20 border-t border-line pt-12">
      <h2 className="text-3xl">{title}</h2>
      <ul className="mt-8 grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-4 lg:gap-x-8">
        {items.slice(0, limit).map((p) => {
          const price = displayPrice({ base_price: p.base_price, compare_at_price: p.compare_at_price, sale_price: p.sale_price });
          return (
            <li key={p.id} className="group relative">
              <div className="mat">
                <div className="relative aspect-[4/5] overflow-hidden bg-sand">
                  <ProductImage src={p.image ?? undefined} alt={p.title} sizes="(min-width: 640px) 22vw, 46vw" />
                </div>
              </div>
              <h3 className="mt-3 font-serif text-base leading-snug">
                <Link href={hrefFor(p.slug)} className="after:absolute after:inset-0">
                  {p.title}
                </Link>
              </h3>
              <p className="mt-1 text-sm text-muted">
                <span className={price.compareAt ? "text-sale" : undefined}>{formatPrice(price.amount, "USD", locale)}</span>
                {price.compareAt && price.compareAt > price.amount && <s className="ml-2 text-xs">{formatPrice(price.compareAt, "USD", locale)}</s>}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
