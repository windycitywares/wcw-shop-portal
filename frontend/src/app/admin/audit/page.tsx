"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { dateTime } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Entry {
  id: number;
  actor_email: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  summary: string | null;
  created_at: string;
}

const PAGE_SIZE = 50;

/** Who changed what, newest first: settings, promotions, campaigns, reviews. */
export default function AdminAudit() {
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: Entry[]; total: number; actions: string[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const p = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    if (action) p.set("action", action);
    apiFetch<{ items: Entry[]; total: number; actions: string[] }>(`/admin/audit?${p}`).then(
      (d) => {
        setData(d);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [q, action, page]);

  const columns: Column<Entry>[] = [
    { key: "when", header: "When", cell: (e) => <span className="whitespace-nowrap text-sm">{dateTime(e.created_at)}</span> },
    { key: "who", header: "Who", cell: (e) => <span className="text-sm">{e.actor_email ?? "System"}</span> },
    {
      key: "what",
      header: "What",
      cell: (e) => (
        <span className="text-sm">
          {e.summary ?? e.action}
          <span className="block font-mono text-xs text-muted">{e.action}</span>
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Audit log" description="Every change staff made to settings, promotions, campaigns and reviews, with who did it and when." />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <Panel>
        <form
          className="flex flex-wrap items-center gap-3 px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(draft.trim());
            setPage(1);
          }}
        >
          <label htmlFor="audit-search" className="sr-only">
            Search the audit log
          </label>
          <Input id="audit-search" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Words, email or code" className="h-9 max-w-xs" />
          <Button type="submit" size="sm" variant="secondary">
            Search
          </Button>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">Kind</span>
            <select
              className="h-9 rounded-lg border border-line bg-surface px-2"
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Everything</option>
              {(data?.actions ?? []).map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </label>
        </form>
        <DataTable columns={columns} rows={data?.items ?? null} rowKey={(e) => e.id} caption="Audit log" empty="Nothing recorded yet." />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} className="px-4 py-3" />}
      </Panel>
    </div>
  );
}
