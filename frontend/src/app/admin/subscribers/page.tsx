"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { downloadFile } from "@/components/admin/download";
import { dateTime } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { IconButton, RowActions } from "@/components/admin/ui/IconButton";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Subscriber {
  id: number;
  email: string;
  locale: string | null;
  source: string;
  subscribed: boolean;
  subscribed_at: string;
  unsubscribed_at: string | null;
  welcome_coupon: string | null;
  has_ordered: boolean;
}
interface Listing {
  items: Subscriber[];
  total: number;
  counts: { all: number; subscribed: number; unsubscribed: number };
}

type Status = "all" | "subscribed" | "unsubscribed";
const SOURCES: Record<string, string> = { site: "Website form", checkout: "Checkout", account: "Account", admin: "Added by staff" };
const LANGUAGES: Record<string, string> = { en: "English", es: "Spanish", nl: "Dutch" };
const PAGE_SIZE = 25;

export default function AdminSubscribers() {
  const { can } = useAuth();
  const { push } = useToast();
  const [status, setStatus] = useState<Status>("subscribed");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Listing | null>(null);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState("");
  const [removing, setRemoving] = useState<Subscriber | null>(null);
  const [deleting, setDeleting] = useState<Subscriber | null>(null);
  const [busy, setBusy] = useState(false);
  const canManage = can("promotions:manage");

  // The bell links here with ?q=email.
  useEffect(() => {
    const found = new URLSearchParams(window.location.search).get("q");
    if (found) {
      setQ(found);
      setDraft(found);
      setStatus("all");
    }
  }, []);

  const query = useCallback(() => {
    const p = new URLSearchParams({ status, page: String(page), page_size: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    return p;
  }, [status, q, page]);

  const load = useCallback(async () => {
    try {
      setData(await apiFetch<Listing>(`/admin/subscribers?${query()}`));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load subscribers");
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setAddError("");
    try {
      await apiFetch("/admin/subscribers", { method: "POST", body: JSON.stringify({ email: fd.get("email"), locale: fd.get("locale") }) });
      push({ title: "Subscriber added", description: String(fd.get("email")) });
      setAdding(false);
      await load();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Could not add this address");
    }
  }

  async function unsubscribe() {
    if (!removing) return;
    setBusy(true);
    try {
      await apiFetch(`/admin/subscribers/${removing.id}/unsubscribe`, { method: "POST" });
      push({ title: "Taken off the list", description: removing.email });
      setRemoving(null);
      await load();
    } catch (err) {
      push({ title: "Not changed", description: err instanceof Error ? err.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await apiFetch(`/admin/subscribers/${deleting.id}`, { method: "DELETE" });
      push({ title: "Subscriber deleted", description: deleting.email });
      setDeleting(null);
      await load();
    } catch (err) {
      push({ title: "Not deleted", description: err instanceof Error ? err.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<Subscriber>[] = [
    {
      key: "email",
      header: "Email",
      cell: (s) => (
        <div className="min-w-0">
          <p className="max-w-[20rem] truncate font-medium">{s.email}</p>
          <p className="text-xs text-muted">
            {LANGUAGES[s.locale ?? "en"] ?? s.locale}
            {s.has_ordered ? " · has ordered" : ""}
          </p>
        </div>
      ),
    },
    { key: "status", header: "Status", cell: (s) => <Pill tone={s.subscribed ? "success" : "neutral"}>{s.subscribed ? "Subscribed" : "Unsubscribed"}</Pill> },
    { key: "source", header: "Joined from", hide: "md", cell: (s) => <span className="text-sm">{SOURCES[s.source] ?? s.source}</span> },
    {
      key: "joined",
      header: "Joined",
      hide: "sm",
      cell: (s) => (
        <span className="text-sm text-muted">
          {dateTime(s.subscribed_at)}
          {s.unsubscribed_at ? ` · left ${dateTime(s.unsubscribed_at)}` : ""}
        </span>
      ),
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (s) =>
        canManage ? (
          <RowActions>
            {s.subscribed && <IconButton icon="archive" label={`Take ${s.email} off the list`} onClick={() => setRemoving(s)} />}
            <IconButton icon="trash" tone="danger" label={`Delete ${s.email}`} onClick={() => setDeleting(s)} />
          </RowActions>
        ) : null,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Subscribers"
        description="Everyone who joined the newsletter from the site, at checkout or in their account. Email campaigns go to the subscribed people on this list."
        actions={
          <>
            <Button size="sm" variant="secondary" onClick={() => downloadFile(`/admin/subscribers/export.csv?${query()}`, "wcw-subscribers.csv").catch((e) => setError(e.message))}>
              Export CSV
            </Button>
            {canManage && (
              <Button size="sm" onClick={() => setAdding(true)}>
                Add subscriber
              </Button>
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
        <Tabs<Status>
          label="Subscriber status"
          value={status}
          onChange={(s) => {
            setStatus(s);
            setPage(1);
          }}
          tabs={[
            { id: "subscribed", label: "Subscribed", count: data?.counts.subscribed },
            { id: "unsubscribed", label: "Unsubscribed", count: data?.counts.unsubscribed },
            { id: "all", label: "Everyone", count: data?.counts.all },
          ]}
          className="px-4"
        />
        <form
          role="search"
          className="flex flex-wrap items-center gap-3 px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(draft.trim());
            setPage(1);
          }}
        >
          <label htmlFor="subscriber-search" className="sr-only">
            Search subscribers
          </label>
          <Input id="subscriber-search" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Email address" className="h-9 max-w-xs" />
          <Button type="submit" size="sm" variant="secondary">
            Search
          </Button>
        </form>
        <DataTable
          caption="Newsletter subscribers"
          columns={columns}
          rows={data ? data.items : null}
          rowKey={(s) => s.id}
          empty={q ? "No one matches that search." : "No subscribers here yet. People join from the form in the footer of the shop."}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
      </Panel>

      <p className="mt-4 text-sm text-muted">
        People can leave with the link in every email. You can take someone off the list or delete their record, but only they can sign up again, so nobody is
        added back without agreeing.
      </p>

      <Modal
        open={adding}
        onClose={() => setAdding(false)}
        title="Add a subscriber"
        description="For someone who asked to join in person or by email. No welcome offer is sent."
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button type="submit" form="add-subscriber-form" size="sm">
              Add subscriber
            </Button>
          </>
        }
      >
        <form id="add-subscriber-form" onSubmit={onAdd} className="space-y-4">
          {addError && <Alert tone="danger">{addError}</Alert>}
          <Field label="Email">{(p) => <Input {...p} name="email" type="email" required autoComplete="off" />}</Field>
          <Field label="Language" hint="The language of the emails they receive.">
            {(p) => (
              <Select {...p} name="locale" defaultValue="en">
                {Object.entries(LANGUAGES).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!removing}
        title="Take this address off the list?"
        tone="primary"
        confirmLabel="Take off the list"
        busy={busy}
        onCancel={() => setRemoving(null)}
        onConfirm={() => void unsubscribe()}
        message={<p>{removing?.email} will not get any more newsletters or campaigns. Only they can sign up again.</p>}
      />
      <ConfirmDialog
        open={!!deleting}
        title="Delete this subscriber?"
        confirmLabel="Delete subscriber"
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={() => void remove()}
        message={<p>The record for {deleting?.email} is removed for good. Use this for a data-deletion request; otherwise taking them off the list keeps proof they opted out.</p>}
      />
    </div>
  );
}
