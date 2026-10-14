"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { InboxMessage, Page } from "@/lib/types";
import { fmtDateTime } from "@/components/admin/orders/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

const PAGE_SIZE = 25;
type Status = InboxMessage["status"];
const LABEL: Record<Status, string> = { new: "New", answered: "Answered", archived: "Archived" };
const TONE: Record<Status, Tone> = { new: "accent", answered: "success", archived: "neutral" };
const TABS = [
  { id: "new", label: "New" },
  { id: "answered", label: "Answered" },
  { id: "archived", label: "Archived" },
  { id: "all", label: "All" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function AdminMessages() {
  const { push } = useToast();
  const [tab, setTab] = useState<TabId>("new");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<InboxMessage> | null>(null);
  const [counts, setCounts] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<InboxMessage | null>(null);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (tab !== "all") params.set("status", tab);
    if (q) params.set("q", q);
    setLoading(true);
    try {
      const [list, c] = await Promise.all([
        apiFetch<Page<InboxMessage>>(`/messages?${params}`),
        apiFetch<{ counts: Record<string, number> }>("/messages/counts"),
      ]);
      setData(list);
      setCounts(c.counts);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load messages");
    } finally {
      setLoading(false);
    }
  }, [page, tab, q]);

  useEffect(() => {
    void load();
  }, [load]);

  const tabs = useMemo(
    () => TABS.map((t) => ({ id: t.id, label: t.label, count: counts ? (t.id === "all" ? Object.values(counts).reduce((a, b) => a + b, 0) : (counts[t.id] ?? 0)) : undefined })),
    [counts],
  );

  async function update(message: InboxMessage, body: { status?: Status; admin_note?: string | null }, done: string) {
    try {
      const saved = await apiFetch<InboxMessage>(`/messages/${message.id}`, { method: "PATCH", body: JSON.stringify(body) });
      push({ title: done });
      setOpen(saved);
      await load();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't save");
      return false;
    }
  }

  const columns: Column<InboxMessage>[] = [
    {
      key: "from",
      header: "From",
      cell: (m) => (
        <button type="button" onClick={() => setOpen(m)} className="block min-w-0 max-w-xs text-left">
          <span className={`block truncate ${m.status === "new" ? "font-semibold" : "font-medium"} hover:underline`}>{m.name}</span>
          <span className="block truncate text-xs text-muted">{m.email}</span>
        </button>
      ),
    },
    {
      key: "subject",
      header: "Subject",
      hide: "sm",
      cell: (m) => (
        <div className="min-w-0 max-w-md">
          <p className="truncate">{m.subject}</p>
          <p className="truncate text-xs text-muted">{m.message}</p>
        </div>
      ),
    },
    { key: "order", header: "Order", hide: "lg", cell: (m) => (m.order_number ? <span className="font-mono text-xs">{m.order_number}</span> : <span className="text-muted">—</span>) },
    { key: "when", header: "Received", hide: "md", cell: (m) => <span className="text-muted">{fmtDateTime(m.created_at)}</span> },
    { key: "status", header: "Status", cell: (m) => <Pill tone={TONE[m.status]}>{LABEL[m.status]}</Pill> },
  ];

  return (
    <div>
      <PageHeader title="Messages" description="Everything sent through the contact form. Reply from your own email, then mark the message answered." />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <Panel>
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 px-2 pt-1">
          <Tabs
            label="Filter messages"
            tabs={tabs}
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
            <label htmlFor="message-q" className="sr-only">
              Search messages
            </label>
            <div className="relative">
              <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <input
                id="message-q"
                name="q"
                type="search"
                placeholder="Name, email or subject"
                className="h-8 w-56 rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-2 text-sm placeholder:text-muted/70 focus-visible:border-accent"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm" className="h-8">
              Search
            </Button>
          </form>
        </div>
        <div className="border-t border-line">
          <DataTable
            caption="Messages"
            columns={columns}
            rows={data ? data.items : null}
            rowKey={(m) => m.id}
            loading={loading}
            empty={q ? "No message matches that search." : tab === "new" ? "Nothing new. You're all caught up." : "Nothing here."}
          />
          {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}
        </div>
      </Panel>
      <MessageDialog message={open} onClose={() => setOpen(null)} onUpdate={update} />
    </div>
  );
}

function MessageDialog({
  message,
  onClose,
  onUpdate,
}: {
  message: InboxMessage | null;
  onClose: () => void;
  onUpdate: (m: InboxMessage, body: { status?: Status; admin_note?: string | null }, done: string) => Promise<boolean>;
}) {
  const [note, setNote] = useState("");
  useEffect(() => {
    setNote(message?.admin_note ?? "");
  }, [message]);
  const reply = message ? `mailto:${message.email}?subject=${encodeURIComponent(`Re: ${message.subject}`)}` : "#";
  return (
    <Modal
      open={message != null}
      onClose={onClose}
      size="lg"
      title={message?.subject ?? "Message"}
      description={message ? `From ${message.name} · ${fmtDateTime(message.created_at)}` : undefined}
      footer={
        message && (
          <>
            {message.status !== "archived" && (
              <Button variant="ghost" size="sm" className="h-9" onClick={() => onUpdate(message, { status: "archived" }, "Archived")}>
                Archive
              </Button>
            )}
            {message.status === "new" ? (
              <Button variant="secondary" size="sm" className="h-9" onClick={() => onUpdate(message, { status: "answered" }, "Marked answered")}>
                Mark answered
              </Button>
            ) : (
              <Button variant="secondary" size="sm" className="h-9" onClick={() => onUpdate(message, { status: "new" }, "Moved back to new")}>
                Mark as new
              </Button>
            )}
            <a
              href={reply}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-[var(--radius-control)] bg-accent px-4 text-sm font-medium text-on-accent hover:bg-accent-strong"
            >
              <Icon name="mail" className="size-4" />
              Reply by email
            </a>
          </>
        )
      }
    >
      {message && (
        <div className="space-y-5 text-sm">
          {!message.emailed && <Alert tone="info">The email alert for this message did not send, so it only exists here.</Alert>}
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted">Email</dt>
              <dd>
                <a href={`mailto:${message.email}`} className="text-accent hover:underline">
                  {message.email}
                </a>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Status</dt>
              <dd>
                <Pill tone={TONE[message.status]}>{LABEL[message.status]}</Pill>
              </dd>
            </div>
            {message.order_number && (
              <div>
                <dt className="text-xs text-muted">About order</dt>
                <dd>
                  <Link href={`/admin/orders/${message.order_number}`} className="font-mono text-accent hover:underline">
                    {message.order_number}
                  </Link>
                </dd>
              </div>
            )}
            {message.locale && (
              <div>
                <dt className="text-xs text-muted">Language</dt>
                <dd className="uppercase">{message.locale}</dd>
              </div>
            )}
          </dl>
          <p className="whitespace-pre-line rounded-[var(--radius-control)] bg-canvas p-4 leading-relaxed">{message.message}</p>
          <form
            className="space-y-3"
            onSubmit={async (e) => {
              e.preventDefault();
              await onUpdate(message, { admin_note: note.trim() || null }, "Note saved");
            }}
          >
            <Field label="Internal note" hint="Only your team sees this.">
              {(p) => <Textarea {...p} value={note} onChange={(e) => setNote(e.target.value)} maxLength={4000} className="min-h-20" />}
            </Field>
            <Button type="submit" variant="secondary" size="sm" disabled={note === (message.admin_note ?? "")}>
              Save note
            </Button>
          </form>
        </div>
      )}
    </Modal>
  );
}
