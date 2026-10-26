"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { dateTime, timeAgo } from "@/components/admin/charts/format";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

import { LiveUpdatesBar, updates } from "@/components/admin/live/LiveUpdatesBar";
interface Row {
  id: number;
  product_id: number;
  title: string;
  slug: string;
  sku: string | null;
  variant: string | null;
  in_stock: boolean;
  email: string;
  options: Record<string, string>;
  note: string | null;
  kind: "restock" | "request";
  status: "waiting" | "notified" | "closed";
  created_at: string;
  notified_at: string | null;
  closed_at: string | null;
  handled_by_email: string | null;
}
interface List {
  items: Row[];
  total: number;
  counts: { restock: number; request: number };
}

type View = "request" | "restock" | "done";
const PAGE_SIZE = 25;
const describe = (o: Record<string, string>) => Object.entries(o).map(([k, v]) => `${k}: ${v}`).join(" · ");

/** What customers asked for: sold-out items (emailed automatically when back) and combinations the shop doesn't sell. */
export default function AdminStockRequests() {
  const { push } = useToast();
  const [view, setView] = useState<View>("request");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<List | null>(null);
  const [error, setError] = useState("");
  const [answering, setAnswering] = useState<Row | null>(null);
  const [message, setMessage] = useState("");
  const [closing, setClosing] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    const p = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), status: view === "done" ? "done" : "waiting" });
    if (view !== "done") p.set("kind", view);
    if (q) p.set("q", q);
    apiFetch<List>(`/admin/stock-requests?${p}`).then(
      (d) => {
        setData(d);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [view, page, q]);
  useEffect(load, [load]);
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get("view");
    if (v === "restock" || v === "done" || v === "request") setView(v);
  }, []);

  async function notify() {
    if (!answering) return;
    setBusy(true);
    try {
      await apiFetch(`/admin/stock-requests/${answering.id}/notify`, { method: "POST", body: JSON.stringify({ message: message.trim() || null }) });
      push({ title: "Customer emailed", description: `${answering.email}: ${answering.title}` });
      setAnswering(null);
      load();
    } catch (e) {
      push({ title: "Not sent", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Stock requests"
        description="Signed-in customers ask to be told when something is available. Back-in-stock requests are emailed automatically when you add stock; special requests are for combinations you don't sell yet and wait for your answer."
      />
      <LiveUpdatesBar prefixes={["stock_request."]} describe={updates("new requests")} onRefresh={() => void load()} />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <Panel>
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line px-4 pt-3">
          <Tabs<View>
            label="Requests"
            value={view}
            onChange={(v) => {
              setView(v);
              setPage(1);
            }}
            tabs={[
              { id: "request", label: "Special requests", count: data?.counts.request },
              { id: "restock", label: "Waiting for stock", count: data?.counts.restock },
              { id: "done", label: "Answered" },
            ]}
          />
          <form
            className="flex gap-2 pb-3"
            onSubmit={(e) => {
              e.preventDefault();
              setQ(draft.trim());
              setPage(1);
            }}
          >
            <label htmlFor="request-search" className="sr-only">
              Search requests
            </label>
            <Input id="request-search" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Email, product or SKU" className="h-9" />
            <Button type="submit" size="sm" variant="secondary">
              Search
            </Button>
          </form>
        </div>
        {data === null ? (
          <div className="skeleton m-5 h-24" />
        ) : data.items.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-muted">{view === "done" ? "Nothing answered yet." : "No requests waiting."}</p>
        ) : (
          <ul className="divide-y divide-line">
            {data.items.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start gap-x-4 gap-y-2 px-5 py-4">
                <div className="min-w-0 flex-1 basis-72 space-y-1 text-sm">
                  <p className="flex flex-wrap items-center gap-2">
                    <Link href={`/admin/products/${r.product_id}`} className="font-medium hover:underline">
                      {r.title}
                    </Link>
                    <Pill tone={r.kind === "request" ? "accent" : "info"}>{r.kind === "request" ? "Special request" : "Back in stock"}</Pill>
                    {r.status !== "waiting" && <Pill tone={r.status === "notified" ? "success" : "neutral"}>{r.status === "notified" ? "Emailed" : "Closed"}</Pill>}
                    {r.status === "waiting" && r.kind === "restock" && r.in_stock && <Pill tone="success">In stock now</Pill>}
                  </p>
                  {Object.keys(r.options).length > 0 && <p className="font-medium">{describe(r.options)}</p>}
                  {r.note && <p className="whitespace-pre-line rounded bg-sand/60 px-3 py-2">{r.note}</p>}
                  <p className="text-xs text-muted">
                    {r.email} · asked {timeAgo(r.created_at)}
                    {r.sku ? ` · ${r.sku}` : ""}
                    {r.status !== "waiting" && (r.notified_at || r.closed_at) && ` · ${r.status === "notified" ? "emailed" : "closed"} ${dateTime((r.notified_at || r.closed_at) as string)}${r.handled_by_email ? ` by ${r.handled_by_email}` : ""}`}
                  </p>
                </div>
                {r.status === "waiting" && (
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        setAnswering(r);
                        setMessage("");
                      }}
                    >
                      Email: it&apos;s available
                      <span className="sr-only"> ({r.email})</span>
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setClosing(r)}>
                      Close
                      <span className="sr-only"> request from {r.email}</span>
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} className="px-4 py-3" />}
      </Panel>

      <Modal
        open={!!answering}
        onClose={() => !busy && setAnswering(null)}
        title="Tell the customer it's available"
        description={answering ? `${answering.email} · ${answering.title}${Object.keys(answering.options).length ? ` (${describe(answering.options)})` : ""}` : undefined}
        footer={
          <>
            <Button size="sm" variant="secondary" onClick={() => setAnswering(null)} disabled={busy}>
              Cancel
            </Button>
            <Button size="sm" onClick={notify} disabled={busy}>
              {busy ? "Sending…" : "Send email"}
            </Button>
          </>
        }
      >
        <label htmlFor="answer-message" className="text-sm font-medium">
          Personal message (optional)
        </label>
        <Textarea
          id="answer-message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          maxLength={1000}
          className="mt-1 min-h-24"
          placeholder="We can make it in Walnut. It ships within a week of your order."
        />
        <p className="mt-2 text-xs text-muted">The email says it can be ordered now and links to the product. Make sure the option can actually be bought first.</p>
      </Modal>

      <ConfirmDialog
        open={!!closing}
        title="Close this request?"
        message="No email is sent. The customer sees the request as closed in their account."
        confirmLabel="Close request"
        tone="danger"
        busy={busy}
        onConfirm={async () => {
          if (!closing) return;
          setBusy(true);
          try {
            await apiFetch(`/admin/stock-requests/${closing.id}/close`, { method: "POST" });
            push({ title: "Request closed", description: closing.email });
            setClosing(null);
            load();
          } catch (e) {
            push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
          } finally {
            setBusy(false);
          }
        }}
        onCancel={() => setClosing(null)}
      />
    </div>
  );
}
