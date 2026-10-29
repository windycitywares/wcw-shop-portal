"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { downloadFile } from "@/components/admin/download";
import { dateTime } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { IconLink, RowActions } from "@/components/admin/ui/IconButton";
import { CrmNotice } from "@/components/admin/CrmNotice";
import { crmLink } from "@/lib/crm";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

import { LiveUpdatesBar, updates } from "@/components/admin/live/LiveUpdatesBar";
interface Subscriber {
  id: number;
  email: string;
  locale: string | null;
  source: string;
  subscribed: boolean;
  subscribed_at: string;
  unsubscribed_at: string | null;
  paused: boolean;
  paused_at: string | null;
  welcome_coupon: string | null;
  has_ordered: boolean;
}
interface Listing {
  items: Subscriber[];
  total: number;
  counts: { all: number; subscribed: number; paused: number; unsubscribed: number };
}

type Status = "all" | "subscribed" | "paused" | "unsubscribed";
const SOURCES: Record<string, string> = { site: "Website form", checkout: "Checkout", account: "Account", admin: "Added by staff" };
const LANGUAGES: Record<string, string> = { en: "English", es: "Spanish", nl: "Dutch" };
const PAGE_SIZE = 25;

export default function AdminSubscribers() {
  const [status, setStatus] = useState<Status>("subscribed");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Listing | null>(null);
  const [error, setError] = useState("");

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
    {
      key: "status",
      header: "Status",
      cell: (s) =>
        s.paused ? (
          <Pill tone="warning">Paused</Pill>
        ) : (
          <Pill tone={s.subscribed ? "success" : "neutral"}>{s.subscribed ? "Subscribed" : "Unsubscribed"}</Pill>
        ),
    },
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
      cell: (s) => (
        <RowActions>
          <IconLink icon="external" label={`Open ${s.email} in the CRM`} href={crmLink(`/customers?q=${encodeURIComponent(s.email)}`)} />
        </RowActions>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Subscribers"
        description="Everyone who joined the newsletter from the site, at checkout or in their account."
        actions={
          <Button size="sm" variant="secondary" onClick={() => downloadFile(`/admin/subscribers/export.csv?${query()}`, "wcw-subscribers.csv").catch((e) => setError(e.message))}>
            Export CSV
          </Button>
        }
      />
      <CrmNotice what="Subscribers" path="/customers" action="Open customers in the CRM" />
      <LiveUpdatesBar prefixes={["subscriber."]} describe={updates("subscriber updates")} onRefresh={() => void load()} />
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
            { id: "paused", label: "Paused", count: data?.counts.paused },
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

    </div>
  );
}
