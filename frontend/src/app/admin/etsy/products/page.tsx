"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/client-api";
import { ShopTabs } from "@/components/admin/ShopTabs";
import { dateTime, money } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Variation {
  sku: string | null;
  options: Record<string, string>;
  price: string | null;
  quantity: number | null;
}
interface Listing {
  id: number;
  etsy_listing_id: number;
  title: string;
  state: string;
  price: string | null;
  currency: string;
  quantity: number | null;
  skus: string[];
  url: string | null;
  image: string | null;
  variations: Variation[];
  description: string | null;
  synced_at: string;
  internal_supplier: string | null;
  internal_purchase_cost: string | null;
  internal_notes: string | null;
}
interface Page {
  items: Listing[];
  total: number;
  page: number;
  page_size: number;
}

const PAGE_SIZE = 25;
const STATES: [string, string][] = [
  ["", "All listings"], ["active", "Active"], ["inactive", "Inactive"], ["sold_out", "Sold out"],
  ["draft", "Draft"], ["expired", "Expired"], ["removed", "Removed from Etsy"],
];
const TONE: Record<string, Tone> = { active: "success", inactive: "neutral", sold_out: "warning", draft: "neutral", expired: "neutral", removed: "danger" };
const LABEL = Object.fromEntries(STATES.filter(([k]) => k));
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

export default function EtsyProducts() {
  const { push } = useToast();
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [editing, setEditing] = useState<Listing | null>(null);
  const [supplier, setSupplier] = useState("");
  const [cost, setCost] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
      if (query) p.set("q", query);
      if (state) p.set("state", state);
      setData(await apiFetch<Page>(`/admin/etsy/listings?${p}`));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [page, query, state]);
  useEffect(() => {
    void load();
  }, [load]);

  const open = (l: Listing) => {
    setEditing(l);
    setSupplier(l.internal_supplier ?? "");
    setCost(l.internal_purchase_cost ?? "");
    setNotes(l.internal_notes ?? "");
  };
  const save = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await apiFetch(`/admin/etsy/listings/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify({ internal_supplier: supplier.trim() || null, internal_purchase_cost: cost.trim() || null, internal_notes: notes.trim() || null }),
      });
      push({ title: "Internal info saved" });
      setEditing(null);
      void load();
    } catch (e) {
      push({ title: "Not saved", description: errorText(e), tone: "danger" });
    } finally {
      setSaving(false);
    }
  };
  const syncNow = async () => {
    setSyncing(true);
    try {
      const r = await apiFetch<{ error?: string; skipped?: string; total?: number }>("/admin/etsy/sync", { method: "POST" });
      if (r.error) push({ title: "Sync failed", description: r.error, tone: "danger" });
      else if (r.skipped) push({ title: "Not synced", description: `Etsy is ${r.skipped}.`, tone: "danger" });
      else push({ title: "Synced from Etsy", description: `${r.total ?? 0} listings.` });
      void load();
    } catch (e) {
      push({ title: "Sync failed", description: errorText(e), tone: "danger" });
    } finally {
      setSyncing(false);
    }
  };

  const columns: Column<Listing>[] = [
    {
      key: "title",
      header: "Listing",
      cell: (l) => (
        <button type="button" onClick={() => open(l)} className="flex min-w-0 items-center gap-3 text-left focus-visible:outline-2 focus-visible:outline-accent">
          {l.image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={l.image} alt="" className="size-10 shrink-0 rounded-md object-cover" loading="lazy" />
          ) : (
            <span className="size-10 shrink-0 rounded-md bg-canvas" aria-hidden="true" />
          )}
          <span className="min-w-0">
            <span className="block truncate font-medium">{l.title}</span>
            <span className="block truncate text-xs text-muted">{l.skus.join(", ") || "No SKU"}</span>
          </span>
        </button>
      ),
    },
    { key: "state", header: "Status", cell: (l) => <Pill tone={TONE[l.state] ?? "neutral"}>{LABEL[l.state] ?? l.state}</Pill> },
    { key: "price", header: "Etsy price", align: "right", cell: (l) => (l.price ? money(Number(l.price), { cents: true }) : "—") },
    { key: "qty", header: "In stock", align: "right", hide: "sm", cell: (l) => l.quantity ?? "—" },
    { key: "supplier", header: "Supplier", hide: "md", cell: (l) => l.internal_supplier ?? <span className="text-muted">Not set</span> },
    { key: "cost", header: "Our cost", align: "right", hide: "md", cell: (l) => (l.internal_purchase_cost ? money(Number(l.internal_purchase_cost), { cents: true }) : <span className="text-muted">Not set</span>) },
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader
        title="Etsy listings"
        description="Read from Etsy every 15 minutes. Etsy details can't be edited here; add your default supplier, cost and notes."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href="/admin/settings?tab=external_shops&shop=etsy" className="inline-flex items-center rounded-md px-3 py-2 text-sm font-medium text-accent underline">Etsy connection</Link>
            <Button variant="secondary" onClick={syncNow} disabled={syncing}>{syncing ? "Syncing…" : "Sync from Etsy now"}</Button>
          </div>
        }
      />
      <ShopTabs shop="etsy" />
      {error ? <Alert tone="danger">{error}</Alert> : null}
      <Panel>
        <form
          className="flex flex-wrap items-end gap-3 border-b border-line p-4"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setQuery(q.trim());
          }}
        >
          <Field label="Search listings" className="min-w-52 flex-1">{(p) => <Input {...p} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Title or SKU" />}</Field>
          <Field label="Status" className="w-48">
            {(p) => (
              <Select {...p} value={state} onChange={(e) => { setPage(1); setState(e.target.value); }}>
                {STATES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            )}
          </Field>
          <Button type="submit">Search</Button>
        </form>
        <DataTable
          columns={columns}
          rows={data ? data.items : null}
          rowKey={(l) => l.id}
          caption="Etsy listings"
          loading={loading}
          empty="No listings yet. Connect Etsy, then press “Sync from Etsy now”."
        />
        {data ? <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} /> : null}
      </Panel>

      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing?.title ?? "Listing"}
        description="Etsy's details are read-only. These three fields are only for your team."
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? "Saving…" : "Save internal info"}</Button>
          </>
        }
      >
        {editing ? (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-muted">Etsy price</dt>
              <dd className="text-right">{editing.price ? money(Number(editing.price), { cents: true }) : "—"}</dd>
              <dt className="text-muted">In stock</dt>
              <dd className="text-right">{editing.quantity ?? "—"}</dd>
              <dt className="text-muted">Last synced</dt>
              <dd className="text-right">{dateTime(editing.synced_at)}</dd>
            </dl>
            {editing.variations.length > 0 ? (
              <ul className="divide-y divide-line rounded-md border border-line text-sm">
                {editing.variations.map((v, i) => (
                  <li key={i} className="flex flex-wrap justify-between gap-2 px-3 py-2">
                    <span>{Object.entries(v.options).map(([k, val]) => `${k}: ${val}`).join(" · ") || v.sku || "Variation"}</span>
                    <span className="text-muted">{v.price ? money(Number(v.price), { cents: true }) : ""}{v.quantity != null ? ` · ${v.quantity} in stock` : ""}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {editing.url ? <a href={editing.url} target="_blank" rel="noopener noreferrer" className="text-sm text-accent underline">Open on Etsy (new tab)</a> : null}
            <Field label="Default supplier">{(p) => <Input {...p} value={supplier} onChange={(e) => setSupplier(e.target.value)} maxLength={200} />}</Field>
            <Field label="Default purchase cost per unit ($)" hint="New orders for this listing start with this cost.">
              {(p) => <Input {...p} inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} />}
            </Field>
            <Field label="Internal notes">{(p) => <Textarea {...p} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={5000} />}</Field>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
