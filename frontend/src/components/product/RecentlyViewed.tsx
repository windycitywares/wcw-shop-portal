"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { recentlyViewed, type ProductCardData } from "@/lib/engagement";
import { MiniCards } from "./MiniCards";

/** Remembers this product in the browser and shows the others viewed before it. Nothing leaves the browser. */
export function RecentlyViewed({ current }: { current: ProductCardData }) {
  const { t, href, locale } = useI18n();
  const [items, setItems] = useState<ProductCardData[]>([]);
  useEffect(() => {
    setItems(recentlyViewed.read().filter((p) => p.id !== current.id));
    recentlyViewed.remember(current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current.id]);
  return <MiniCards items={items} title={t.discover.recent} hrefFor={(slug) => href(`/product/${slug}`)} locale={locale} />;
}
