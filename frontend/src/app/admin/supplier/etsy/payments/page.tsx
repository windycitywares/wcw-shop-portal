"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/client-api";
import { downloadFile } from "@/components/admin/download";
import { dateTime, fmtInt, money } from "@/components/admin/charts/format";
import { PAYMENT_LABEL, PAYMENT_TONE } from "@/components/admin/etsy/supplier";
import { Stat } from "@/components/admin/etsy/ui";
import { ShopTabs } from "@/components/admin/ShopTabs";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";

type State = "pending" | "settled" | "all";
interface Row {
  id: number;
  etsy_receipt_id: number;
  ordered_at: string;
  supplier_order_number: string | null;
  items: string;
  owed: string | null;
  payment_status: keyof typeof PAYMENT_LABEL;
  paid_at: string | null;
  paid_amount: string | null;
  payment_ref: string | null;
}
interface Data {
  pending_count: number;
  pending_amount: string;
  settled_count: number;
  settled_amount: string;
  items: Row[];
  total: number;
}
const PAGE_SIZE = 50;
const m = (v: string | null | undefined) => (v == null ? "—" : money(Number(v), { cents: true }));

/** What the shop owes this supplier, and what it has paid — with an export for their books. */
export default function SupplierPayments() {
  const { push } = useToast();
  const [state, setState] = useState<State>("pending");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setData(await apiFetch<Data>(`/supplier/etsy/payments?state=${state}&page=${page}&page_size=${PAGE_SIZE}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  }, [state, page]);
  useEffect(() => {
    void load();
  }, [load]);

  const exportAs = (format: "csv" | "xlsx") =>
    downloadFile(`/supplier/etsy/payments/export?state=${state}&format=${format}`, `payments-${state}.${format}`).catch((e) =>
      push({ title: "Export failed", description: e instanceof Error ? e.message : undefined, tone: "danger" }));

  const columns: Column<Row>[] = [
    { key: "o", header: "Order", cell: (r) => <Link href={`/admin/supplier/etsy/orders/${r.id}`} className="font-medium text-accent hover:underline">#{r.etsy_receipt_id}<span className="block text-xs font-normal text-muted">{dateTime(r.ordered_at)}</span></Link> },
    { key: "ref", header: "Your order #", hide: "sm", cell: (r) => r.supplier_order_number ?? "—" },
    { key: "i", header: "Items", hide: "md", cell: (r) => <span className="line-clamp-2 max-w-72">{r.items}</span> },
    { key: "a", header: "Amount", align: "right", cell: (r) => <span className="num">{m(r.owed)}</span> },
    { key: "s", header: "Payment", cell: (r) => <Pill tone={PAYMENT_TONE[r.payment_status]}>{PAYMENT_LABEL[r.payment_status]}</Pill> },
    { key: "p", header: "Paid", hide: "sm", cell: (r) => (r.paid_at ? <span className="text-sm">{m(r.paid_amount)} on {r.paid_at.slice(0, 10)}{r.payment_ref ? <span className="block text-xs text-muted">{r.payment_ref}</span> : null}</span> : "—") },
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader
        title="Your payments"
        description="What Windy City Wares owes you for Etsy orders (item + shipping) and what has been paid."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => exportAs("csv")}>Export CSV</Button>
            <Button size="sm" variant="secondary" onClick={() => exportAs("xlsx")}>Export Excel</Button>
          </div>
        }
      />
      <ShopTabs shop="etsy" permission="supplier:portal" />
      {error ? <Alert tone="danger">{error}</Alert> : null}
      <div className="grid grid-cols-2 gap-4">
        <Stat label="Not paid yet" value={data ? m(data.pending_amount) : "—"} sub={data ? `${fmtInt(data.pending_count)} orders` : undefined} tone={data?.pending_count ? "warning" : undefined}
          active={state === "pending"} onClick={() => { setState("pending"); setPage(1); }} />
        <Stat label="Paid" value={data ? m(data.settled_amount) : "—"} sub={data ? `${fmtInt(data.settled_count)} orders` : undefined} tone="success"
          active={state === "settled"} onClick={() => { setState("settled"); setPage(1); }} />
      </div>
      <Panel>
        <Tabs<State> label="Payments" className="px-4" value={state} onChange={(v) => { setState(v); setPage(1); }}
          tabs={[{ id: "pending", label: "Not paid yet", count: data?.pending_count }, { id: "settled", label: "Paid", count: data?.settled_count }, { id: "all", label: "All" }]} />
        <DataTable columns={columns} rows={data ? data.items : null} rowKey={(r) => r.id} caption="Your payments" empty="Nothing here yet." />
        {data ? <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} /> : null}
      </Panel>
    </div>
  );
}
