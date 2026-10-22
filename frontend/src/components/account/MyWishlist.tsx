"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { wishlistApi } from "@/lib/engagement";
import type { ProductCardData } from "@/lib/types";
import { MiniCards } from "@/components/product/MiniCards";

/** Designs the shopper saved with the heart button. */
export function MyWishlist() {
  const { t, href, locale } = useI18n();
  const [items, setItems] = useState<ProductCardData[] | null>(null);
  useEffect(() => {
    wishlistApi
      .list(locale)
      .then(setItems)
      .catch(() => setItems([]));
  }, [locale]);
  if (items === null) return null;
  if (!items.length) {
    return (
      <section id="my-wishlist" aria-labelledby="my-wishlist-heading" className="mt-12 scroll-mt-24">
        <h2 id="my-wishlist-heading" className="text-3xl">
          {t.wishlist.title}
        </h2>
        <p className="mt-4 text-sm text-muted">{t.wishlist.empty}</p>
      </section>
    );
  }
  return <MiniCards id="my-wishlist" items={items} title={t.wishlist.title} hrefFor={(slug) => href(`/product/${slug}`)} locale={locale} limit={48} />;
}
