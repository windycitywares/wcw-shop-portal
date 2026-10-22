"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { dateTime } from "@/components/admin/charts/format";
import { ConfirmDialog } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { useToast } from "@/components/admin/ui/Toast";
import { IconButton } from "@/components/admin/ui/IconButton";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Review {
  id: number;
  product_id: number;
  product_title: string;
  product_slug: string;
  author_name: string;
  rating: number;
  title: string | null;
  body: string;
  status: "pending" | "approved" | "rejected";
  verified: boolean;
  helpful_count: number;
  reply: string | null;
  created_at: string;
}

type Status = "pending" | "approved" | "rejected";
const PAGE_SIZE = 20;

export default function AdminReviews() {
  const { push } = useToast();
  const [status, setStatus] = useState<Status>("pending");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: Review[]; total: number; counts: Record<Status, number> } | null>(null);
  const [replies, setReplies] = useState<Record<number, string>>({});
  const [deleting, setDeleting] = useState<Review | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const s = new URLSearchParams(window.location.search).get("status");
    if (s === "approved" || s === "rejected" || s === "pending") setStatus(s);
  }, []);

  const load = useCallback(() => {
    const p = new URLSearchParams({ status, page: String(page), page_size: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    apiFetch<{ items: Review[]; total: number; counts: Record<Status, number> }>(`/admin/reviews?${p}`).then(
      (d) => {
        setData(d);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [status, page, q]);
  useEffect(load, [load]);

  async function moderate(r: Review, next: Status) {
    try {
      const reply = replies[r.id] ?? r.reply ?? "";
      await apiFetch(`/admin/reviews/${r.id}`, { method: "PUT", body: JSON.stringify({ status: next, reply: reply.trim() || null }) });
      push({ title: next === "approved" ? "Review published" : next === "rejected" ? "Review hidden" : "Review moved back", description: r.product_title });
      load();
    } catch (e) {
      push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    }
  }

  return (
    <div>
      <PageHeader
        title="Reviews"
        description="Reviews appear on the product page once you publish them. Verified buyers bought the design; reviews with links always wait here."
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <Panel>
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line px-4 pt-3">
          <Tabs
            tabs={[
              { id: "pending", label: "To approve", count: data?.counts.pending },
              { id: "approved", label: "Published", count: data?.counts.approved },
              { id: "rejected", label: "Hidden", count: data?.counts.rejected },
            ]}
            value={status}
            onChange={(id) => {
              setStatus(id as Status);
              setPage(1);
            }}
            label="Review status"
          />
          <form
            className="flex gap-2 pb-3"
            onSubmit={(e) => {
              e.preventDefault();
              setQ(draft.trim());
              setPage(1);
            }}
          >
            <label htmlFor="review-search" className="sr-only">
              Search reviews
            </label>
            <Input id="review-search" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Words, product or name" className="h-9" />
            <Button type="submit" size="sm" variant="secondary">
              Search
            </Button>
          </form>
        </div>
        {data === null ? (
          <div className="skeleton m-5 h-24" />
        ) : data.items.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-muted">
            {status === "pending" ? "Nothing waiting. New reviews appear here as soon as they're written." : "No reviews here."}
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {data.items.map((r) => (
              <li key={r.id} className="space-y-3 px-5 py-4">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                  <span aria-label={`${r.rating} out of 5 stars`} className="text-accent">
                    {"★".repeat(r.rating)}
                    <span className="text-line">{"★".repeat(5 - r.rating)}</span>
                  </span>
                  <a href={`/product/${r.product_slug}#reviews`} target="_blank" rel="noopener noreferrer" className="font-medium hover:underline">
                    {r.product_title}
                    <span className="sr-only"> (opens the product in a new tab)</span>
                  </a>
                  <span className="text-muted">
                    {r.author_name} · {dateTime(r.created_at)}
                  </span>
                  {r.verified && <Pill tone="success">Verified buyer</Pill>}
                  {r.helpful_count > 0 && <span className="text-xs text-muted">{r.helpful_count} found it helpful</span>}
                </div>
                {r.title && <p className="font-medium">{r.title}</p>}
                <p className="whitespace-pre-line text-sm leading-relaxed">{r.body}</p>
                <div>
                  <label htmlFor={`reply-${r.id}`} className="text-sm font-medium">
                    Public reply (optional)
                  </label>
                  <Textarea
                    id={`reply-${r.id}`}
                    value={replies[r.id] ?? r.reply ?? ""}
                    onChange={(e) => setReplies({ ...replies, [r.id]: e.target.value })}
                    maxLength={2000}
                    className="mt-1 min-h-16"
                    placeholder="Thank them, or answer a question. Shown under the review."
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  {r.status !== "approved" && (
                    <Button size="sm" onClick={() => moderate(r, "approved")}>
                      Publish
                      <span className="sr-only"> review of {r.product_title}</span>
                    </Button>
                  )}
                  {r.status === "approved" && (
                    <Button size="sm" variant="secondary" onClick={() => moderate(r, "approved")}>
                      Save reply
                    </Button>
                  )}
                  {r.status !== "rejected" && (
                    <Button size="sm" variant="secondary" onClick={() => moderate(r, "rejected")}>
                      Hide
                      <span className="sr-only"> review of {r.product_title}</span>
                    </Button>
                  )}
                  <IconButton icon="trash" tone="danger" label={`Delete review of ${r.product_title}`} onClick={() => setDeleting(r)} />
                </div>
              </li>
            ))}
          </ul>
        )}
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} className="px-4 py-3" />}
      </Panel>

      <ConfirmDialog
        open={!!deleting}
        title="Delete this review?"
        message="It's removed for good and the product's rating is recalculated. Hiding it keeps it on record instead."
        confirmLabel="Delete review"
        tone="danger"
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await apiFetch(`/admin/reviews/${deleting.id}`, { method: "DELETE" });
            push({ title: "Review deleted" });
            setDeleting(null);
            load();
          } catch (e) {
            push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
          }
        }}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
