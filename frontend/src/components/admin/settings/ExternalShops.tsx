"use client";

import { useState } from "react";
import { Tabs } from "@/components/admin/ui/Tabs";
import { EtsyConnection } from "./EtsyConnection";

/** Every marketplace that can be connected, one tab each. To add Amazon or Walmart: add a line here and its own panel. */
const SHOPS = [{ id: "etsy", label: "Etsy", panel: () => <EtsyConnection /> }] as const;
type ShopId = (typeof SHOPS)[number]["id"];

export function ExternalShops() {
  const [shop, setShop] = useState<ShopId>(() => {
    const wanted = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("shop");
    return SHOPS.find((s) => s.id === wanted)?.id ?? SHOPS[0].id;
  });
  const current = SHOPS.find((s) => s.id === shop) ?? SHOPS[0];
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <Tabs
        label="External shops"
        tabs={SHOPS.map((s) => ({ id: s.id, label: s.label }))}
        value={shop}
        onChange={(id) => {
          setShop(id);
          const url = new URL(window.location.href);
          url.searchParams.set("shop", id);
          window.history.replaceState(null, "", url);
        }}
      />
      <div role="tabpanel" aria-label={current.label}>{current.panel()}</div>
    </div>
  );
}
