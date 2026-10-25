"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { useLiveSignal } from "@/lib/useLiveSignal";
import { Icon } from "../ui/Icon";
import { Popover } from "@/components/ui/Popover";
import { ActivityRow, type Feed } from "./shared";

const SAFETY_MS = 60_000; // reload now and then whatever else happens

/** Bell in the admin header: a count of new activity, the latest items, and a link to everything. */
export function NotificationBell() {
  const [feed, setFeed] = useState<Feed | null>(null);

  const load = useCallback(() => {
    apiFetch<Feed>("/admin/notifications?limit=12").then(setFeed, () => undefined);
  }, []);

  useEffect(() => {
    load();
    const safety = window.setInterval(() => document.visibilityState === "visible" && load(), SAFETY_MS);
    return () => window.clearInterval(safety);
  }, [load]);
  const live = useLiveSignal("admin", "/admin/notifications/pulse", true, load);

  async function opened(open: boolean) {
    if (!open) return;
    const fresh = await apiFetch<Feed>("/admin/notifications?limit=12").catch(() => null);
    if (fresh) setFeed(fresh);
    if ((fresh ?? feed)?.unread) {
      // The list keeps its "new" marks while it's open; the badge clears.
      await apiFetch("/admin/notifications/seen", { method: "POST" }).catch(() => undefined);
      setFeed((f) => (f ? { ...f, unread: 0 } : f));
    }
  }

  const unread = feed?.unread ?? 0;
  return (
    <Popover
      label={unread ? `Notifications, ${unread} new` : "Notifications"}
      title="Notifications"
      onOpenChange={opened}
      trigger={
        <span className="relative grid place-items-center">
          <Icon name="bell" className="size-5" />
          {unread > 0 && (
            <span aria-hidden="true" className="num absolute -right-2 -top-1.5 min-w-4 rounded-full bg-danger px-1 text-center text-[10px] font-semibold leading-4 text-white">
              {unread > 98 ? "99+" : unread}
            </span>
          )}
        </span>
      }
      triggerClassName="border-transparent bg-transparent px-2 hover:border-line"
      panelClassName="w-[22rem] max-w-[calc(100vw-1.5rem)] p-0"
    >
      {(close) => (
        <div>
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="text-sm font-semibold">Activity</p>
            <Link href="/admin/notifications" onClick={close} className="text-xs font-medium text-accent underline underline-offset-4">
              See all activity
            </Link>
          </div>
          {feed === null ? (
            <div className="skeleton m-4 h-20" />
          ) : feed.items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-muted">Nothing new in the last 30 days.</p>
          ) : (
            <ul className="max-h-[min(28rem,70dvh)] overflow-y-auto p-1.5">
              {feed.items.map((item) => (
                <li key={item.id}>
                  <ActivityRow item={item} onNavigate={close} compact />
                </li>
              ))}
            </ul>
          )}
          <p className="border-t border-line px-4 py-2 text-xs text-muted" data-testid="bell-live-status" data-mode={live}>
            {live === "stream" ? "Live: new activity appears within about two seconds" : live === "polling" ? "Checking for new activity every 10 seconds" : "Connecting…"}
          </p>
        </div>
      )}
    </Popover>
  );
}
