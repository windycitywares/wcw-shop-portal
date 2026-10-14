"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import type { ContentStatus, Page, Product } from "@/lib/types";
import { STATUS_LABEL, formatPrice } from "@/lib/utils";
import { Pagination } from "@/components/admin/ui/Pagination";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { useToast } from "@/components/admin/ui/Toast";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";
import { ProductImage } from "@/components/ui/ProductImage";

const ALL: ContentStatus[] = ["draft", "in_review", "published", "archived"];
const TONE: Record<ContentStatus, Tone> = { draft: "neutral", in_review: "accent", published: "success", archived: "warning" };
const TABS = [
  { id: "all", label: "All" },
  { id: "published", label: "Published" },
  { id: "in_review", label: "In review" },
  { id: "draft", label: "Draft" },
  { id: "archived", label: "Archived" },
];
const PAGE_SIZE = 25;

export default function AdminProducts() {
  const { can } = useAuth();
  const { push } = useToast();
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Product> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("status");
    if (initial && TABS.some((t) => t.id === initial)) setTab(initial);
  }, []);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), sort: "updated" });
    (tab === "all" ? ALL : [tab]).forEach((s) => params.append("status", s));
    if (q) params.set("q", q);
    setLoading(true);
    try {
      setData(await apiFetch<Page<Product>>(`/products?${params}`));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [page, tab, q]);

  useEffect(() => {
    void load();
  }, [load]);

  async function changeStatus(p: Product, next: ContentStatus) {
    try {
      await apiFetch(`/products/${p.id}/status`, { method: "POST", body: JSON.stringify({ status: next }) });
      push({ title: next === "published" ? "Published" : next === "in_review" ? "Sent for review" : "Unpublished", description: p.title });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  }

  const canPublish = can("catalog:publish");

  const columns: Column<Product>[] = [
    {
      key: "product",
      header: "Product",
      cell: (p) => (
        <div className="flex min-w-0 items-center gap-3">
          <div className="relative size-10 shrink-0 overflow-hidden rounded bg-sand">
            <ProductImage src={p.images[0]?.url} alt="" sizes="40px" />
          </div>
          <div className="min-w-0">
            <Link href={`/admin/products/${p.id}`} className="line-clamp-2 max-w-[26rem] font-medium hover:underline sm:line-clamp-none sm:block sm:truncate">
              {p.title}
            </Link>
            <span className="block text-xs text-muted">
              <span className="font-mono">{p.sku}</span> · from {p.source}
            </span>
            <span className="mt-1 block md:hidden">
              <Pill tone={TONE[p.status]}>{STATUS_LABEL[p.status]}</Pill>
            </span>
          </div>
        </div>
      ),
    },
    {
      key: "price",
      header: "Price",
      align: "right",
      cell: (p) => (
        <span className="num">
          {formatPrice(p.base_price, p.currency)}
          {p.compare_at_price != null && p.compare_at_price > p.base_price && (
            <s className="ml-1.5 text-xs text-muted">{formatPrice(p.compare_at_price, p.currency)}</s>
          )}
        </span>
      ),
    },
    {
      key: "stock",
      header: "In stock",
      align: "right",
      hide: "sm",
      cell: (p) =>
        p.stock_status === "out_of_stock" ? (
          <Pill tone="danger">Sold out</Pill>
        ) : p.stock_quantity != null && p.stock_quantity <= 3 ? (
          <span className="num text-warning">{p.stock_quantity} left</span>
        ) : (
          <span className="num">{p.stock_quantity ?? "—"}</span>
        ),
    },
    { key: "status", header: "Status", hide: "md", cell: (p) => <Pill tone={TONE[p.status]}>{STATUS_LABEL[p.status]}</Pill> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      hide: "md",
      cell: (p) => (
        <div className="flex justify-end gap-2">
          {p.status === "draft" && (
            <Button size="sm" variant="secondary" className="h-8" onClick={() => changeStatus(p, "in_review")}>
              Submit for review
            </Button>
          )}
          {canPublish && p.status !== "published" && (
            <Button size="sm" className="h-8" onClick={() => changeStatus(p, "published")}>
              Publish
            </Button>
          )}
          {canPublish && p.status === "published" && (
            <Button size="sm" variant="ghost" className="h-8" onClick={() => changeStatus(p, "archived")}>
              Unpublish
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Products"
        description="Everything in the shop, from your Etsy listings and imports. Publish when a listing is ready to be seen."
        actions={
          <>
            <ButtonLink href="/admin/import" variant="secondary" size="sm" className="h-9">
              <Icon name="import" className="size-4" />
              Import
            </ButtonLink>
            {can("catalog:create") && (
              <ButtonLink href="/admin/products/new" size="sm" className="h-9">
                <Icon name="plus" className="size-4" />
                Add product
              </ButtonLink>
            )}
          </>
        }
      />

      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}

      <Panel>
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 px-2 pt-1">
          <Tabs
            label="Filter by status"
            tabs={TABS}
            value={tab}
            onChange={(id) => {
              setPage(1);
              setTab(id);
            }}
            className="border-b-0"
          />
          <form
            role="search"
            className="flex items-center gap-2 pb-2 pr-2"
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              setQ(String(new FormData(e.currentTarget).get("q") || "").trim());
            }}
          >
            <label htmlFor="admin-q" className="sr-only">
              Search products
            </label>
            <div className="relative">
              <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <input
                id="admin-q"
                name="q"
                type="search"
                placeholder="Title or SKU"
                className="h-8 w-52 rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-2 text-sm placeholder:text-muted/70 focus-visible:border-accent"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm" className="h-8">
              Search
            </Button>
          </form>
        </div>
        <div className="border-t border-line">
          <DataTable
            caption="Products"
            columns={columns}
            rows={data ? data.items : null}
            rowKey={(p) => p.id}
            loading={loading && !!data}
            empty={
              <span>
                No products match.{" "}
                <Link href="/admin/import" className="text-accent underline">
                  Import from Etsy, Amazon or a spreadsheet
                </Link>
              </span>
            }
          />
        </div>
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}
      </Panel>
    </div>
  );
}
