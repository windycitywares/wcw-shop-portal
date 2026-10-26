"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { ActivityRow, KIND, type Activity, type Feed } from "@/components/admin/notifications/shared";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel } from "@/components/admin/ui/Panel";
import { Tabs } from "@/components/admin/ui/Tabs";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";

type Filter = "all" | Activity["type"];
const PAGE = 40;

/** Everything from the bell, last 30 days, filterable by kind, each linking to where it's handled. */
export default function AdminNotifications() {
  const [filter, setFilter] = useState<Filter>("all");
  const [items, setItems] = useState<Activity[] | null>(null);
  const [kinds, setKinds] = useState<Activity["type"][]>([]);
  const [more, setMore] = useState(false);
  const [error, setError] = useState("");

  const fetchPage = useCallback(
    (before?: string) => {
      const p = new URLSearchParams({ limit: String(PAGE) });
      if (filter !== "all") p.set("kind", filter);
      if (before) p.set("before", before);
      return apiFetch<Feed>(`/admin/notifications?${p}`);
    },
    [filter],
  );

  useEffect(() => {
    setItems(null);
    fetchPage().then(
      (f) => {
        setItems(f.items);
        setKinds(f.kinds);
        setMore(f.items.length === PAGE);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [fetchPage]);

  useEffect(() => {
    apiFetch("/admin/notifications/seen", { method: "POST" }).catch(() => undefined);
  }, []);

  return (
    <div>
      <PageHeader
        title="Activity"
        description="What happened in the shop in the last 30 days. Select an item to open it where it's handled."
        actions={
          <ButtonLink href="/admin/notifications/settings" size="sm" variant="secondary">
            Notification settings
          </ButtonLink>
        }
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <Panel>
        <div className="px-4 pt-3">
          <Tabs<Filter>
            label="Show"
            value={filter}
            onChange={setFilter}
            tabs={[{ id: "all" as Filter, label: "All" }, ...kinds.map((k) => ({ id: k as Filter, label: KIND[k].label }))]}
          />
        </div>
        {items === null ? (
          <div className="skeleton m-5 h-32" />
        ) : items.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-muted">Nothing here in the last 30 days.</p>
        ) : (
          <ul className="divide-y divide-line p-1.5">
            {items.map((item) => (
              <li key={item.id}>
                <ActivityRow item={item} />
              </li>
            ))}
          </ul>
        )}
        {more && items && (
          <div className="border-t border-line px-4 py-3">
            <Button
              size="sm"
              variant="secondary"
              onClick={async () => {
                const f = await fetchPage(items[items.length - 1].at);
                setItems([...items, ...f.items]);
                setMore(f.items.length === PAGE);
              }}
            >
              Show older activity
            </Button>
          </div>
        )}
      </Panel>
    </div>
  );
}
