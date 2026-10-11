import Link from "next/link";
import type { Product } from "@/lib/types";
import { Badge, Price } from "@/components/ui/misc";
import { ProductImage } from "@/components/ui/ProductImage";

export function ProductCard({ product, priority }: { product: Product; priority?: boolean }) {
  const image = product.images[0];
  const soldOut = product.stock_status === "out_of_stock";
  return (
    <article className="group relative">
      <div className="relative aspect-[4/5] overflow-hidden rounded-[var(--radius-card)] bg-sand">
        <ProductImage
          src={image?.url}
          alt={image?.alt || product.title}
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
          priority={priority}
          className="transition-transform duration-500 group-hover:scale-[1.03]"
        />
        {soldOut && <Badge className="absolute left-3 top-3">Sold out</Badge>}
      </div>
      <h3 className="mt-3 font-sans text-sm font-medium leading-snug">
        {/* The stretched link makes the whole card clickable with one tab stop */}
        <Link href={`/product/${product.slug}`} className="after:absolute after:inset-0 hover:underline">
          {product.title}
        </Link>
      </h3>
      <Price
        amount={product.base_price}
        compareAt={product.compare_at_price}
        currency={product.currency}
        className="mt-1 text-sm text-muted"
      />
    </article>
  );
}

export function ProductGrid({ products, priorityCount = 0 }: { products: Product[]; priorityCount?: number }) {
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 lg:grid-cols-4 lg:gap-x-6">
      {products.map((p, i) => (
        <li key={p.id}>
          <ProductCard product={p} priority={i < priorityCount} />
        </li>
      ))}
    </ul>
  );
}
