"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Empty, Loading, ReportHeader, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { BarList } from "@/components/admin/charts/BarList";
import { fmtInt, money } from "@/components/admin/charts/format";
import { rate } from "@/components/admin/reports";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";

interface ProductRow {
  id: number;
  title: string;
  slug: string;
  sku: string | null;
  price: number | null;
  stock: number | null;
  rating: number | null;
  rating_count: number;
  units: number;
  orders: number;
  merchandise: number;
  profit: number | null;
  margin: number | null;
  return_rate: number | null;
  views: number;
  viewers: number;
  carted: number;
  wishlist_adds: number;
  view_to_cart: number | null;
  conversion: number | null;
  revenue_share: number | null;
  abc: "A" | "B" | "C" | null;
}

interface ProductsReport {
  range: RangeInfo;
  summary: {
    products: number;
    sold: number;
    units: number;
    merchandise: number;
    views: number;
    wishlist_adds: number;
    abc: Record<"A" | "B" | "C" | "unsold", { count: number; revenue: number; share: number | null }>;
  };
  products: ProductRow[];
  viewed_not_bought: { id: number; title: string; views: number; viewers: number; carted: number }[];
  bought_together: { first_id: number; second_id: number; first_title: string; second_title: string; orders: number }[];
  reviews: {
    approved: number;
    pending: number;
    average: number | null;
    critical_unanswered: number;
    new_in_range: number;
    distribution: { rating: number; count: number }[];
    lowest_rated: { id: number; title: string; rating_avg: number; rating_count: number }[];
    requests: { orders: number; requested: number; reviewed: number; review_rate: number | null };
  };
}

type SortKey = "merchandise" | "units" | "viewers" | "conversion" | "margin" | "rating";
const ABC_TONE: Record<"A" | "B" | "C", Tone> = { A: "success", B: "info", C: "neutral" };
const PAGE_SIZE = 25;

export default function ProductsReportPage() {
  const { range, setRange, data, error } = useReport<ProductsReport>("products");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "merchandise", dir: "desc" });
  const [page, setPage] = useState(1);

  const rows = useMemo(() => {
    const list = [...(data?.products ?? [])];
    const value = (p: ProductRow) => p[sort.key] ?? -1;
    list.sort((a, b) => (sort.dir === "desc" ? value(b) - value(a) : value(a) - value(b)) || a.id - b.id);
    return list;
  }, [data, sort]);

  const s = data?.summary;
  const r = data?.reviews;
  const columns: Column<ProductRow>[] = [
    {
      key: "product",
      header: "Product",
      cell: (p) => (
        <div className="min-w-0">
          <Link href={`/admin/products/${p.id}`} className="block max-w-[18rem] truncate font-medium hover:underline">
            {p.title}
          </Link>
          <span className="flex items-center gap-2 text-xs text-muted">
            {p.abc && <Pill tone={ABC_TONE[p.abc]}>Class {p.abc}</Pill>}
            {p.sku}
            {p.stock != null && ` · ${p.stock} in stock`}
          </span>
        </div>
      ),
    },
    { key: "revenue", header: "Revenue", align: "right", sort: "merchandise", cell: (p) => <span className="num">{money(p.merchandise)}</span> },
    { key: "units", header: "Sold", align: "right", sort: "units", cell: (p) => <span className="num">{fmtInt(p.units)}</span> },
    { key: "viewers", header: "Visitors", align: "right", sort: "viewers", hide: "md", cell: (p) => <span className="num">{fmtInt(p.viewers)}</span> },
    {
      key: "conversion",
      header: "Conversion",
      align: "right",
      sort: "conversion",
      hide: "md",
      cell: (p) => (
        <span className="num" title="Visitors who viewed the product and then bought it">
          {rate(p.conversion)}
        </span>
      ),
    },
    { key: "margin", header: "Margin", align: "right", sort: "margin", hide: "lg", cell: (p) => <span className="num">{rate(p.margin, 0)}</span> },
    {
      key: "rating",
      header: "Rating",
      align: "right",
      sort: "rating",
      hide: "lg",
      cell: (p) => <span className="num text-sm">{p.rating != null ? `${p.rating.toFixed(1)} (${p.rating_count})` : "—"}</span>,
    },
  ];

  return (
    <div>
      <ReportHeader
        title="Product performance"
        description="What sells, what gets looked at but not bought, and what customers say. Views count visitors who accepted analytics; sales are complete."
        range={range}
        onRange={setRange}
        exportKind="products"
        error={error}
      />
      <MetricStrip
        items={[
          { label: "Products sold", value: s ? `${s.sold} of ${s.products}` : "—", hint: "Published products with at least one sale" },
          { label: "Items sold", value: s ? fmtInt(s.units) : "—" },
          { label: "Merchandise", value: s ? money(s.merchandise) : "—", hint: "After item discounts, before shipping and tax" },
          { label: "Product views", value: s ? fmtInt(s.views) : "—" },
          { label: "Wishlist saves", value: s ? fmtInt(s.wishlist_adds) : "—" },
        ]}
      />

      <Panel className="mt-6">
        <PanelHeader
          title="ABC analysis"
          description="Class A products earn the first 80% of revenue, B the next 15%, C the last 5%. Keep A items in stock and well photographed; question C items."
        />
        <PanelBody>
          {s ? (
            <MetricStrip
              items={(["A", "B", "C", "unsold"] as const).map((k) => ({
                label: k === "unsold" ? "Not sold" : `Class ${k}`,
                value: `${s.abc[k].count} product${s.abc[k].count === 1 ? "" : "s"}`,
                hint: k === "unsold" ? "No sales in this period" : `${money(s.abc[k].revenue)} · ${rate(s.abc[k].share, 0)} of revenue`,
              }))}
            />
          ) : (
            <Loading />
          )}
        </PanelBody>
      </Panel>

      <Panel className="mt-6">
        <PanelHeader title="Every product" description="Select a column heading to sort." />
        <DataTable
          columns={columns}
          rows={data ? rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : null}
          rowKey={(p) => p.id}
          caption="Product performance"
          empty="No published products yet."
          sort={sort}
          onSort={(key) => {
            setSort((cur) => ({ key: key as SortKey, dir: cur.key === key && cur.dir === "desc" ? "asc" : "desc" }));
            setPage(1);
          }}
        />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} className="px-4 py-3" />}
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Looked at, not bought" description="Products with at least 10 visitors and no sale. Check the price, photos and description." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.viewed_not_bought.map((p) => ({ label: p.title, value: p.views, display: `${p.views} views`, sub: `${p.viewers} visitors · ${p.carted} added to cart`, href: `/admin/products/${p.id}` }))}
                color="var(--color-warning)"
                empty="Nothing here. Either everything popular sells, or there isn't enough traffic yet."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Bought together" description="Pairs that appear in the same order. Good candidates for bundles and recommendations." />
          <PanelBody>
            {!data ? (
              <Loading />
            ) : data.bought_together.length === 0 ? (
              <Empty>No pairs yet. They appear once orders contain more than one design.</Empty>
            ) : (
              <ul className="divide-y divide-line text-sm">
                {data.bought_together.map((p) => (
                  <li key={`${p.first_id}-${p.second_id}`} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="min-w-0">
                      <span className="font-medium">{p.first_title}</span> <span className="text-muted">+</span> <span className="font-medium">{p.second_title}</span>
                    </span>
                    <span className="num shrink-0 text-muted">{p.orders} orders</span>
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader
          title="Reviews"
          description="Published reviews across the shop. Review requests go out by email after delivery."
          actions={
            <Link href="/admin/reviews" className="text-sm font-medium text-accent underline underline-offset-4">
              Moderate reviews
            </Link>
          }
        />
        <PanelBody className="space-y-5">
          {r ? (
            <>
              <MetricStrip
                items={[
                  { label: "Average rating", value: r.average != null ? `${r.average.toFixed(1)} / 5` : "—", hint: `${r.approved} published` },
                  { label: "New in period", value: String(r.new_in_range) },
                  { label: "Waiting to approve", value: String(r.pending) },
                  { label: "Unanswered 1–2 stars", value: String(r.critical_unanswered), hint: "A calm public reply reassures other shoppers" },
                  { label: "Review rate", value: rate(r.requests.review_rate), hint: `${r.requests.reviewed} of ${r.requests.orders} orders` },
                ]}
              />
              <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
                <BarList
                  items={r.distribution.map((d) => ({ label: `${d.rating} star${d.rating === 1 ? "" : "s"}`, value: d.count, display: fmtInt(d.count) }))}
                  empty="No published reviews yet."
                />
                <div>
                  <h3 className="mb-2 text-sm font-medium">Lowest rated</h3>
                  {r.lowest_rated.length === 0 ? (
                    <p className="text-sm text-muted">No ratings yet.</p>
                  ) : (
                    <ul className="divide-y divide-line text-sm">
                      {r.lowest_rated.map((p) => (
                        <li key={p.id} className="flex justify-between gap-3 py-2">
                          <Link href={`/admin/products/${p.id}`} className="min-w-0 truncate hover:underline">
                            {p.title}
                          </Link>
                          <span className="num shrink-0 text-muted">
                            {Number(p.rating_avg).toFixed(1)} ({p.rating_count})
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </>
          ) : (
            <Loading />
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
