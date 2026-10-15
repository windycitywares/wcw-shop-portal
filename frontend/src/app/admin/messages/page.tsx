"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { cn } from "@/lib/utils";
import { dateTime, money, timeAgo } from "@/components/admin/charts/format";
import { ORDER_STATUS } from "@/components/admin/reports";
import { ConfirmDialog } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

type Status = "new" | "open" | "replied" | "closed" | "spam";
type View = "active" | "replied" | "closed" | "spam" | "all";

interface Item {
  id: number;
  name: string;
  email: string;
  subject: string;
  preview: string;
  order_number: string | null;
  status: Status;
  replies: number;
  created_at: string;
}
interface List {
  items: Item[];
  total: number;
  counts: Record<Status | "active" | "all", number>;
}
interface Detail {
  id: number;
  name: string;
  email: string;
  subject: string;
  message: string;
  order_number: string | null;
  order_id: number | null;
  locale: string | null;
  status: Status;
  staff_note: string | null;
  emailed: boolean;
  signed_in: boolean;
  handled_at: string | null;
  handled_by_email: string | null;
  created_at: string;
  replies: { id: number; author_email: string | null; body: string; emailed: boolean; created_at: string }[];
  earlier: { id: number; subject: string; status: Status; created_at: string }[];
  orders: { id: number; number: string; status: string; grand_total: number; placed_at: string | null }[];
}

const STATUS: Record<Status, { label: string; tone: Tone }> = {
  new: { label: "New", tone: "accent" },
  open: { label: "To answer", tone: "warning" },
  replied: { label: "Replied", tone: "success" },
  closed: { label: "Closed", tone: "neutral" },
  spam: { label: "Spam", tone: "danger" },
};
const LANGUAGE: Record<string, string> = { en: "English", es: "Spanish", nl: "Dutch" };
const PAGE_SIZE = 25;

export default function AdminMessages() {
  const { push } = useToast();
  const [view, setView] = useState<View>("active");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [list, setList] = useState<List | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [reply, setReply] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const detailRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    const p = new URLSearchParams({ status: view, page: String(page), page_size: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    apiFetch<List>(`/admin/messages?${p}`).then(
      (d) => {
        setList(d);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [view, page, q]);
  useEffect(load, [load]);

  const show = useCallback((d: Detail) => {
    setDetail(d);
    setNote(d.staff_note ?? "");
  }, []);

  async function open(id: number) {
    setSelected(id);
    setReply("");
    setDetail(null);
    try {
      show(await apiFetch<Detail>(`/admin/messages/${id}`));
      load(); // the badge changes from New to To answer
      requestAnimationFrame(() => detailRef.current?.focus());
    } catch (e) {
      push({ title: "Couldn't open the message", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    }
  }

  async function setStatus(status: Status, done: string) {
    if (!detail) return;
    setBusy(true);
    try {
      show(await apiFetch<Detail>(`/admin/messages/${detail.id}`, { method: "PATCH", body: JSON.stringify({ status }) }));
      push({ title: done, description: detail.subject });
      load();
    } catch (e) {
      push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  async function saveNote() {
    if (!detail) return;
    setBusy(true);
    try {
      show(await apiFetch<Detail>(`/admin/messages/${detail.id}`, { method: "PATCH", body: JSON.stringify({ staff_note: note }) }));
      push({ title: "Note saved" });
    } catch (e) {
      push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(close: boolean) {
    if (!detail || !reply.trim()) return;
    setBusy(true);
    try {
      const out = await apiFetch<{ message: Detail; emailed: boolean }>(`/admin/messages/${detail.id}/reply`, {
        method: "POST",
        body: JSON.stringify({ body: reply, close }),
      });
      show(out.message);
      setReply("");
      push(
        out.emailed
          ? { title: close ? "Reply sent and closed" : "Reply sent", description: `Emailed to ${detail.email}` }
          : { title: "Reply saved, email not sent yet", description: "The scheduled email job will retry it.", tone: "danger" },
      );
      load();
    } catch (e) {
      push({ title: "Reply not sent", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  const c = list?.counts;

  return (
    <div>
      <PageHeader
        title="Messages"
        description="Questions sent from the Contact page. Replies are emailed to the customer from the shop's address, with their message quoted underneath."
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Panel className={cn(selected != null && "max-xl:hidden")}>
          <div className="border-b border-line px-4 pt-3">
            <Tabs<View>
              label="Message status"
              value={view}
              onChange={(v) => {
                setView(v);
                setPage(1);
              }}
              tabs={[
                { id: "active", label: "To answer", count: c?.active },
                { id: "replied", label: "Replied", count: c?.replied },
                { id: "closed", label: "Closed", count: c?.closed },
                { id: "spam", label: "Spam", count: c?.spam },
                { id: "all", label: "All", count: c?.all },
              ]}
            />
            <form
              className="flex gap-2 py-3"
              onSubmit={(e) => {
                e.preventDefault();
                setQ(draft.trim());
                setPage(1);
              }}
            >
              <label htmlFor="message-search" className="sr-only">
                Search messages
              </label>
              <Input id="message-search" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Name, email, words or order number" className="h-9" />
              <Button type="submit" size="sm" variant="secondary">
                Search
              </Button>
            </form>
          </div>
          {list === null ? (
            <PanelBody>
              <div className="skeleton h-32" />
            </PanelBody>
          ) : list.items.length === 0 ? (
            <p className="px-5 py-10 text-center text-sm text-muted">{view === "active" ? "All caught up. New messages appear here." : "No messages here."}</p>
          ) : (
            <ul className="divide-y divide-line">
              {list.items.map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => open(m.id)}
                    aria-current={selected === m.id ? "true" : undefined}
                    className={cn("block w-full px-5 py-3.5 text-left transition-colors hover:bg-sand/60", selected === m.id && "bg-accent-soft/60")}
                  >
                    <span className="flex items-center justify-between gap-3">
                      <span className={cn("min-w-0 truncate text-sm", m.status === "new" ? "font-semibold" : "font-medium")}>{m.name}</span>
                      <span className="shrink-0 text-xs text-muted">{timeAgo(m.created_at)}</span>
                    </span>
                    <span className="mt-0.5 flex items-center gap-2">
                      <Pill tone={STATUS[m.status].tone}>{STATUS[m.status].label}</Pill>
                      <span className="min-w-0 truncate text-sm">{m.subject}</span>
                    </span>
                    <span className="mt-1 line-clamp-2 block text-sm text-muted">{m.preview}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {list && <Pagination page={page} pageSize={PAGE_SIZE} total={list.total} onPage={setPage} className="px-4 py-3" />}
        </Panel>

        <div className={cn(selected == null && "max-xl:hidden")}>
          {selected == null ? (
            <Panel>
              <PanelBody>
                <p className="py-16 text-center text-sm text-muted">Choose a message to read and answer it.</p>
              </PanelBody>
            </Panel>
          ) : !detail ? (
            <Panel>
              <PanelBody>
                <div className="skeleton h-48" />
              </PanelBody>
            </Panel>
          ) : (
            <div ref={detailRef} tabIndex={-1} className="space-y-6 outline-none" aria-label={`Message: ${detail.subject}`} role="region">
              <Button size="sm" variant="ghost" className="xl:hidden" onClick={() => setSelected(null)}>
                ← Back to messages
              </Button>
              <Panel>
                <PanelHeader
                  title={detail.subject}
                  description={`${detail.name} <${detail.email}> · ${dateTime(detail.created_at)}`}
                  actions={<Pill tone={STATUS[detail.status].tone}>{STATUS[detail.status].label}</Pill>}
                />
                <PanelBody className="space-y-4">
                  <p className="whitespace-pre-line text-sm leading-relaxed">{detail.message}</p>
                  <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                    {detail.order_number && (
                      <span>
                        Order{" "}
                        {detail.order_id ? (
                          <Link href={`/admin/orders/${detail.order_id}`} className="num text-accent underline underline-offset-4">
                            {detail.order_number}
                          </Link>
                        ) : (
                          <span className="num">{detail.order_number} (not found)</span>
                        )}
                      </span>
                    )}
                    <span>{detail.signed_in ? "Signed in when sending" : "Sent as a guest"}</span>
                    {detail.locale && <span>Wrote in {LANGUAGE[detail.locale] ?? detail.locale}</span>}
                    {!detail.emailed && <span>The notification email to the shop wasn&apos;t sent</span>}
                  </p>
                </PanelBody>
                {detail.replies.length > 0 && (
                  <ol className="space-y-3 border-t border-line px-5 py-4" aria-label="Replies">
                    {detail.replies.map((r) => (
                      <li key={r.id} className="rounded-[var(--radius-card)] bg-sand/60 px-4 py-3 text-sm">
                        <p className="mb-1 text-xs text-muted">
                          {r.author_email ?? "Staff"} · {dateTime(r.created_at)} · {r.emailed ? "emailed" : "email queued"}
                        </p>
                        <p className="whitespace-pre-line">{r.body}</p>
                      </li>
                    ))}
                  </ol>
                )}
              </Panel>

              {detail.status !== "spam" && (
                <Panel>
                  <PanelHeader title="Reply" description={`Goes to ${detail.email}. Your first name and the shop name are added as a sign-off.`} />
                  <PanelBody className="space-y-3">
                    <label htmlFor="reply-body" className="sr-only">
                      Reply to {detail.name}
                    </label>
                    <Textarea
                      id="reply-body"
                      value={reply}
                      onChange={(e) => setReply(e.target.value)}
                      maxLength={10000}
                      className="min-h-36"
                      placeholder={`Hi ${detail.name.split(" ")[0]},`}
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" disabled={busy || !reply.trim()} onClick={() => sendReply(false)}>
                        Send reply
                      </Button>
                      <Button size="sm" variant="secondary" disabled={busy || !reply.trim()} onClick={() => sendReply(true)}>
                        Send and close
                      </Button>
                    </div>
                  </PanelBody>
                </Panel>
              )}

              <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
                <Panel>
                  <PanelHeader title="Private note" description="Only staff see this." />
                  <PanelBody className="space-y-3">
                    <label htmlFor="staff-note" className="sr-only">
                      Private note
                    </label>
                    <Textarea id="staff-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={5000} className="min-h-20" />
                    <Button size="sm" variant="secondary" disabled={busy || note === (detail.staff_note ?? "")} onClick={saveNote}>
                      Save note
                    </Button>
                  </PanelBody>
                </Panel>
                <Panel>
                  <PanelHeader title="Status" description={detail.handled_by_email && detail.handled_at ? `Last handled by ${detail.handled_by_email}, ${timeAgo(detail.handled_at)}.` : undefined} />
                  <PanelBody className="flex flex-wrap gap-2">
                    {detail.status !== "closed" && detail.status !== "spam" && (
                      <Button size="sm" variant="secondary" disabled={busy} onClick={() => setStatus("closed", "Message closed")}>
                        Close without replying
                      </Button>
                    )}
                    {(detail.status === "closed" || detail.status === "replied" || detail.status === "spam") && (
                      <Button size="sm" variant="secondary" disabled={busy} onClick={() => setStatus("open", "Message moved back to the inbox")}>
                        Move back to inbox
                      </Button>
                    )}
                    {detail.status !== "spam" && (
                      <Button size="sm" variant="ghost" disabled={busy} onClick={() => setStatus("spam", "Marked as spam")}>
                        Mark as spam
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" disabled={busy} onClick={() => setDeleting(true)}>
                      Delete
                    </Button>
                  </PanelBody>
                </Panel>
              </div>

              {(detail.orders.length > 0 || detail.earlier.length > 0) && (
                <Panel>
                  <PanelHeader title="This customer" description={detail.email} />
                  <PanelBody className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
                    <div>
                      <h3 className="mb-2 text-sm font-medium">Orders</h3>
                      {detail.orders.length === 0 ? (
                        <p className="text-sm text-muted">No orders with this email.</p>
                      ) : (
                        <ul className="divide-y divide-line text-sm">
                          {detail.orders.map((o) => (
                            <li key={o.id} className="flex items-center justify-between gap-3 py-2">
                              <Link href={`/admin/orders/${o.id}`} className="num font-medium hover:underline">
                                {o.number}
                              </Link>
                              <span className="flex items-center gap-2">
                                <Pill tone={ORDER_STATUS[o.status]?.tone ?? "neutral"}>{ORDER_STATUS[o.status]?.label ?? o.status}</Pill>
                                <span className="num">{money(o.grand_total)}</span>
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div>
                      <h3 className="mb-2 text-sm font-medium">Earlier messages</h3>
                      {detail.earlier.length === 0 ? (
                        <p className="text-sm text-muted">This is their first message.</p>
                      ) : (
                        <ul className="divide-y divide-line text-sm">
                          {detail.earlier.map((e) => (
                            <li key={e.id}>
                              <button type="button" onClick={() => open(e.id)} className="flex w-full items-center justify-between gap-3 py-2 text-left hover:underline">
                                <span className="min-w-0 truncate">{e.subject}</span>
                                <span className="shrink-0 text-xs text-muted">{timeAgo(e.created_at)}</span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </PanelBody>
                </Panel>
              )}
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={deleting}
        title="Delete this message?"
        message="The message and its replies are removed for good. Closing it keeps it on record instead."
        confirmLabel="Delete message"
        tone="danger"
        busy={busy}
        onConfirm={async () => {
          if (!detail) return;
          setBusy(true);
          try {
            await apiFetch(`/admin/messages/${detail.id}`, { method: "DELETE" });
            push({ title: "Message deleted" });
            setDeleting(false);
            setSelected(null);
            setDetail(null);
            load();
          } catch (e) {
            push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
          } finally {
            setBusy(false);
          }
        }}
        onCancel={() => setDeleting(false)}
      />
    </div>
  );
}
