"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import type { ContentStatus, Page, Product } from "@/lib/types";
import { STATUS_LABEL, formatPrice } from "@/lib/utils";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Alert, Badge, EmptyState } from "@/components/ui/misc";

const ALL: ContentStatus[] = ["draft", "in_review", "published", "archived"];
const TONE = { draft: "neutral", in_review: "accent", published: "success", archived: "danger" } as const;

export default function AdminProducts() {
  const { can } = useAuth();
  const [status, setStatus] = useState<string>("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Product> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("status");
    if (initial) setStatus(initial);
  }, []);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), page_size: "25", sort: "updated" });
    (status ? [status] : ALL).forEach((s) => params.append("status", s));
    if (q) params.set("q", q);
    try {
      setData(await apiFetch<Page<Product>>(`/products?${params}`));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [page, status, q]);

  useEffect(() => {
    void load();
  }, [load]);

  async function changeStatus(p: Product, next: ContentStatus) {
    try {
      await apiFetch(`/products/${p.id}/status`, { method: "POST", body: JSON.stringify({ status: next }) });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  }

  const canPublish = can("catalog:publish");
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-4xl">Products</h1>
        {can("catalog:create") && <ButtonLink href="/admin/products/new">Add product</ButtonLink>}
      </div>

      <form
        className="mt-6 flex flex-wrap gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setQ(String(new FormData(e.currentTarget).get("q") || ""));
        }}
      >
        <label htmlFor="admin-q" className="sr-only">
          Search products
        </label>
        <Input id="admin-q" name="q" placeholder="Title or SKU" className="max-w-xs" />
        <label htmlFor="admin-status" className="sr-only">
          Status
        </label>
        <Select
          id="admin-status"
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value);
          }}
          className="w-44"
        >
          <option value="">All statuses</option>
          {ALL.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </Select>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      {error && <Alert tone="danger" className="mt-4">{error}</Alert>}

      <div className="mt-6 overflow-x-auto rounded-[var(--radius-card)] border border-line bg-surface">
        {data && data.items.length === 0 ? (
          <div className="p-6">
            <EmptyState title="No products found">
              <Link href="/admin/import" className="underline">Import from Etsy, Amazon or a spreadsheet</Link>
            </EmptyState>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Products</caption>
            <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-3">Product</th>
                <th scope="col" className="px-4 py-3">SKU</th>
                <th scope="col" className="px-4 py-3">Price</th>
                <th scope="col" className="px-4 py-3">Stock</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data?.items.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-3">
                    <Link href={`/admin/products/${p.id}`} className="font-medium hover:underline">
                      {p.title}
                    </Link>
                    <span className="block text-xs text-muted">from {p.source}</span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{p.sku}</td>
                  <td className="px-4 py-3">{formatPrice(p.base_price, p.currency)}</td>
                  <td className="px-4 py-3">{p.stock_quantity ?? "—"}</td>
                  <td className="px-4 py-3">
                    <Badge tone={TONE[p.status]}>{STATUS_LABEL[p.status]}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      {p.status === "draft" && (
                        <Button size="sm" variant="secondary" onClick={() => changeStatus(p, "in_review")}>
                          Submit for review
                        </Button>
                      )}
                      {canPublish && p.status !== "published" && (
                        <Button size="sm" onClick={() => changeStatus(p, "published")}>
                          Publish
                        </Button>
                      )}
                      {canPublish && p.status === "published" && (
                        <Button size="sm" variant="ghost" onClick={() => changeStatus(p, "archived")}>
                          Unpublish
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {pages > 1 && (
        <nav aria-label="Pagination" className="mt-6 flex items-center gap-3 text-sm">
          <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <span className="text-muted">
            Page {page} of {pages} · {data?.total} products
          </span>
          <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}
