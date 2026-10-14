import Link from "next/link";
import { localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import type { Product } from "@/lib/types";
import { displayPrice } from "@/lib/utils";
import { Badge, Price } from "@/components/ui/misc";
import { ProductImage } from "@/components/ui/ProductImage";

/** A design shown like a framed print: photo on a white mat, title and price beneath like a wall label. */
export function ProductCard({ product, locale, priority }: { product: Product; locale: Locale; priority?: boolean }) {
  const t = getDictionary(locale);
  const image = product.images[0];
  const soldOut = product.stock_status === "out_of_stock";
  const shown = displayPrice(product);
  const onSale = product.sale_price != null && !soldOut;
  return (
    <article className="group relative">
      <div className="mat transition-colors duration-300 group-hover:border-ink/30">
        <div className="relative aspect-[4/5] overflow-hidden bg-sand">
          <ProductImage
            src={image?.url}
            alt={image?.alt || product.title}
            sizes="(min-width: 1280px) 22vw, (min-width: 640px) 30vw, 46vw"
            priority={priority}
            className="transition-transform duration-700 ease-out group-hover:scale-[1.025]"
          />
          {soldOut && <Badge className="absolute left-2 top-2">{t.product.soldOut}</Badge>}
          {onSale && (
            <Badge tone="accent" className="absolute left-2 top-2 max-w-[80%] truncate">
              {product.sale_label || t.product.sale}
            </Badge>
          )}
        </div>
      </div>
      <h3 className="mt-4 font-serif text-[1.0625rem] font-normal leading-snug sm:text-lg">
        {/* The stretched link makes the whole card clickable with one tab stop */}
        <Link href={localePath(locale, `/product/${product.slug}`)} className="after:absolute after:inset-0">
          {product.title}
        </Link>
      </h3>
      <Price
        amount={shown.amount}
        compareAt={shown.compareAt}
        currency={product.currency}
        locale={locale}
        className="mt-1 text-sm text-muted"
      />
    </article>
  );
}

export function ProductGrid({
  products,
  locale,
  priorityCount = 0,
  columns = 4,
}: {
  products: Product[];
  locale: Locale;
  priorityCount?: number;
  columns?: 3 | 4;
}) {
  return (
    <ul
      className={
        columns === 3
          ? "grid grid-cols-2 gap-x-4 gap-y-12 sm:gap-x-6 md:grid-cols-3 lg:gap-x-8"
          : "grid grid-cols-2 gap-x-4 gap-y-12 sm:grid-cols-3 sm:gap-x-6 lg:grid-cols-4 lg:gap-x-8"
      }
    >
      {products.map((p, i) => (
        <li key={p.id}>
          <ProductCard product={p} locale={locale} priority={i < priorityCount} />
        </li>
      ))}
    </ul>
  );
}
