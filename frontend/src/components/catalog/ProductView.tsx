"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { ProductDetail } from "@/lib/types";

type View = { variantId: number | null; setVariantId: (id: number | null) => void };

const Ctx = createContext<View | null>(null);

/** Shares the chosen variation between the gallery and the purchase panel. */
export function ProductViewProvider({ product, children }: { product: ProductDetail; children: ReactNode }) {
  const [variantId, setVariantId] = useState<number | null>(product.variants[0]?.id ?? null);
  const value = useMemo(() => ({ variantId, setVariantId }), [variantId]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useProductView(): View {
  const v = useContext(Ctx);
  const [variantId, setVariantId] = useState<number | null>(null);
  return v ?? { variantId, setVariantId };
}
