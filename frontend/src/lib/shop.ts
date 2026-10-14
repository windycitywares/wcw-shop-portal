"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "./client-api";
import type { ShopConfig } from "./types";

let pending: Promise<ShopConfig | null> | null = null;

function load() {
  pending ??= apiFetch<ShopConfig>("/shop-config").catch(() => {
    pending = null; // try again next time
    return null;
  });
  return pending;
}

/** Public shop settings (is checkout open, ways to pay, free-shipping threshold). undefined while loading, null if unreachable. */
export function useShopConfig(): ShopConfig | null | undefined {
  const [config, setConfig] = useState<ShopConfig | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    void load().then((c) => live && setConfig(c));
    return () => {
      live = false;
    };
  }, []);
  return config;
}
