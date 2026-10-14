"use client";

import { useEffect, useState } from "react";
import { BatchesTab } from "@/components/admin/promotions/BatchesTab";
import { CouponsTab } from "@/components/admin/promotions/CouponsTab";
import { SalesTab } from "@/components/admin/promotions/SalesTab";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Tabs } from "@/components/admin/ui/Tabs";

const TABS = [
  { id: "coupons", label: "Discount codes" },
  { id: "sales", label: "Sales" },
  { id: "batches", label: "Batches and personal codes" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function AdminPromotions() {
  const [tab, setTab] = useState<TabId>("coupons");

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("tab");
    const found = TABS.find((t) => t.id === initial);
    if (found) setTab(found.id);
  }, []);

  return (
    <div>
      <PageHeader
        title="Promotions"
        description="Run sales, hand out discount codes and see what they earn. Customers type codes in their cart or at checkout."
      />
      <Tabs
        label="Kinds of promotion"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label }))}
        value={tab}
        onChange={setTab}
        className="mb-5"
      />
      {tab === "coupons" && <CouponsTab />}
      {tab === "sales" && <SalesTab />}
      {tab === "batches" && <BatchesTab />}
    </div>
  );
}
