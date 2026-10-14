"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import type { Page, Product } from "@/lib/types";
import { BarList } from "@/components/admin/charts/BarList";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { StatusBar } from "@/components/admin/ui/StatusBar";
import { ButtonLink } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";

type Stats = Record<"draft" | "in_review" | "published" | "archived" | "low_stock", number>;

function greeting(now = new Date()) {
  const h = now.getHours();
  return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

interface Task {
  key: string;
  count: number;
  label: string;
  hint: string;
  href?: string;
  tone: "warning" | "danger" | "info";
}

export default function AdminDashboard() {
  const { user, can } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Stats>("/products/stats").then(setStats, (e) => setError(e.message));
    apiFetch<Page<Product>>("/products?page_size=100&sort=updated&status=published&status=draft&status=in_review").then(
      (r) => setProducts(r.items),
      () => setProducts([]),
    );
  }, []);

  const health = useMemo(() => {
    const list = products ?? [];
    const live = list.filter((p) => p.status === "published");
    return {
      soldOut: live.filter((p) => p.stock_status === "out_of_stock"),
      low: live
        .filter((p) => p.stock_quantity != null && p.stock_quantity > 0 && p.stock_quantity <= 3)
        .sort((a, b) => (a.stock_quantity ?? 0) - (b.stock_quantity ?? 0)),
      noPhoto: live.filter((p) => p.images.length === 0),
      noText: live.filter((p) => !p.description || p.description.length < 80),
    };
  }, [products]);

  const tasks: Task[] = stats
    ? [
        { key: "review", count: stats.in_review, label: "Products waiting for review", hint: "Authors have submitted them for publishing.", href: "/admin/products?status=in_review", tone: "info" as const },
        { key: "soldout", count: health.soldOut.length, label: "Live products are sold out", hint: "Shoppers can see them but can’t buy. Restock or unpublish.", href: "/admin/products?status=published", tone: "danger" as const },
        { key: "low", count: stats.low_stock, label: "Products are almost out of stock", hint: "Three or fewer left.", href: "/admin/products?status=published", tone: "warning" as const },
        { key: "photo", count: health.noPhoto.length, label: "Live products have no photo", hint: "Products with photos get far more clicks.", tone: "warning" as const },
        { key: "text", count: health.noText.length, label: "Live products have a very short description", hint: "A fuller description helps shoppers and search engines.", tone: "warning" as const },
      ].filter((t) => t.count > 0)
    : [];

  return (
    <div>
      <PageHeader
        title={`${greeting()}${user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}`}
        description="Here is the state of the shop."
        actions={
          <>
            {can("catalog:import") && (
              <ButtonLink href="/admin/import" variant="secondary" size="sm">
                Import products
              </ButtonLink>
            )}
            {can("catalog:create") && (
              <ButtonLink href="/admin/products/new" size="sm">
                Add product
              </ButtonLink>
            )}
          </>
        }
      />
      {error && <Alert tone="danger" className="mb-4">{error}</Alert>}

      <MetricStrip
        items={[
          { label: "Live products", value: stats ? String(stats.published) : "—", hint: "Visible in the shop", href: "/admin/products?status=published" },
          { label: "Waiting for review", value: stats ? String(stats.in_review) : "—", hint: "Need a publisher", href: "/admin/products?status=in_review" },
          { label: "Drafts", value: stats ? String(stats.draft) : "—", hint: "Not yet visible", href: "/admin/products?status=draft" },
          { label: "Low stock", value: stats ? String(stats.low_stock) : "—", hint: "Three or fewer left", href: "/admin/products?status=published" },
        ]}
      />

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Needs your attention" description="Small fixes that make the shop easier to buy from." />
          {stats === null ? (
            <PanelBody>
              <div className="skeleton h-24" />
            </PanelBody>
          ) : tasks.length === 0 ? (
            <PanelBody>
              <p className="text-sm text-muted">Nothing needs attention. Every live product has a photo, a description and stock.</p>
            </PanelBody>
          ) : (
            <ul className="divide-y divide-line">
              {tasks.map((t) => (
                <li key={t.key} className="flex items-center gap-4 px-5 py-3.5">
                  <Pill tone={t.tone} dot={false} className="num min-w-9 justify-center text-sm">
                    {t.count}
                  </Pill>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{t.label}</p>
                    <p className="text-sm text-muted">{t.hint}</p>
                  </div>
                  {t.href && (
                    <Link href={t.href} className="shrink-0 text-sm font-medium text-accent underline underline-offset-4">
                      Review
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel>
          <PanelHeader title="Stock running low" description="Fewest units left first." />
          <PanelBody>
            <BarList
              items={health.low.slice(0, 6).map((p) => ({ label: p.title, value: p.stock_quantity ?? 0, display: `${p.stock_quantity} left`, href: `/admin/products/${p.id}` }))}
              max={5}
              color="var(--color-warning)"
              empty={products === null ? "Loading…" : "Everything is comfortably in stock."}
            />
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader title="Catalog" description="Where every product stands in the publishing workflow." />
        <PanelBody>
          <StatusBar
            segments={[
              { label: "Published", value: stats?.published ?? 0, color: "var(--color-success)" },
              { label: "In review", value: stats?.in_review ?? 0, color: "var(--viz-1)" },
              { label: "Draft", value: stats?.draft ?? 0, color: "var(--color-muted)" },
              { label: "Archived", value: stats?.archived ?? 0, color: "var(--color-line)" },
            ]}
          />
        </PanelBody>
      </Panel>
    </div>
  );
}
