"use client";

import { useEffect, useState } from "react";
import { CouponsTab } from "@/components/admin/promotions/CouponsTab";
import { OffersTab } from "@/components/admin/promotions/OffersTab";
import { SalesTab } from "@/components/admin/promotions/SalesTab";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Tabs } from "@/components/admin/ui/Tabs";

type Tab = "sales" | "coupons" | "offers";
const TABS: { id: Tab; label: string }[] = [
  { id: "sales", label: "Sales" },
  { id: "coupons", label: "Coupons" },
  { id: "offers", label: "Cart offers" },
];

export default function AdminPromotions() {
  const [tab, setTab] = useState<Tab>("sales");
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab");
    if (t && TABS.some((x) => x.id === t)) setTab(t as Tab);
  }, []);
  return (
    <div>
      <PageHeader title="Promotions" description="Sale prices, discount codes and automatic offers. The cart and checkout apply them with the same rules." />
      <Tabs
        tabs={TABS}
        value={tab}
        onChange={(id) => {
          setTab(id);
          window.history.replaceState(null, "", `?tab=${id}`);
        }}
        label="Promotion type"
        className="mb-4"
      />
      {tab === "sales" && <SalesTab />}
      {tab === "coupons" && <CouponsTab />}
      {tab === "offers" && <OffersTab />}
    </div>
  );
}
