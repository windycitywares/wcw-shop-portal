"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { API_URL, apiFetch, tokenStore } from "@/lib/client-api";
import { Icon } from "../ui/Icon";
import { Popover } from "@/components/ui/Popover";
import { ActivityRow, type Feed } from "./shared";

const SAFETY_MS = 60_000; // reload now and then whatever else happens
const PULSE_MS = 10_000; // without a WebSocket: ask "anything new?" this often
const HEARTBEAT_MS = 25_000;
const RETRY_AFTER_OPEN_MS = 5_000; // a socket that worked and dropped: try again soon
const RETRY_AFTER_FAIL_MS = 120_000; // a socket that never opened (the host can't do it): don't keep knocking
const OPEN_TIMEOUT_MS = 5_000;

type Pulse = { unread: number; latest: string | null };
/** How the bell hears about new activity: instantly over a WebSocket, or by asking every few seconds. */
type Live = "connecting" | "websocket" | "polling";

const socketUrl = () => `${API_URL.replace(/^http/, "ws")}/admin/notifications/live`;
const signature = (p: Pulse) => `${p.unread}|${p.latest ?? ""}`;

/** Bell in the admin header: a count of new activity, the latest items, and a link to everything. */
export function NotificationBell() {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [live, setLive] = useState<Live>("connecting");

  const load = useCallback(() => {
    apiFetch<Feed>("/admin/notifications?limit=12").then(setFeed, () => undefined);
  }, []);

  useEffect(() => {
    load();
    let stopped = false;
    let last = "";
    let socket: WebSocket | null = null;
    let pollTimer: number | undefined;
    let retryTimer: number | undefined;
    let beatTimer: number | undefined;
    const safety = window.setInterval(() => document.visibilityState === "visible" && load(), SAFETY_MS);

    // Something changed (a new order, a message read in another tab…): reload the feed once per change.
    const changed = (p: Pulse) => {
      const now = signature(p);
      if (now !== last) {
        last = now;
        load();
      }
    };
    const poll = () => {
      if (document.visibilityState !== "visible") return;
      apiFetch<Pulse>("/admin/notifications/pulse").then(changed, () => undefined);
    };
    const startPolling = () => {
      setLive("polling");
      if (pollTimer === undefined) {
        poll();
        pollTimer = window.setInterval(poll, PULSE_MS);
      }
    };
    const stopPolling = () => {
      window.clearInterval(pollTimer);
      pollTimer = undefined;
    };

    const connect = () => {
      const token = tokenStore.get();
      if (stopped || !token || typeof WebSocket === "undefined") return startPolling();
      let opened = false;
      let ws: WebSocket;
      try {
        ws = new WebSocket(socketUrl());
      } catch {
        return startPolling();
      }
      socket = ws;
      const giveUp = window.setTimeout(() => !opened && ws.close(), OPEN_TIMEOUT_MS);
      ws.onopen = () => ws.send(JSON.stringify({ token }));
      ws.onmessage = (e) => {
        let m: { type?: string } & Partial<Pulse>;
        try {
          m = JSON.parse(String(e.data));
        } catch {
          return;
        }
        if (m.type === "hello") {
          opened = true;
          stopPolling();
          setLive("websocket");
          beatTimer = window.setInterval(() => ws.readyState === WebSocket.OPEN && ws.send("ping"), HEARTBEAT_MS);
        } else if (m.type === "pulse") {
          changed({ unread: m.unread ?? 0, latest: m.latest ?? null });
        }
      };
      ws.onclose = () => {
        window.clearTimeout(giveUp);
        window.clearInterval(beatTimer);
        socket = null;
        if (stopped) return;
        startPolling(); // never without news: ask every few seconds until the socket is back
        retryTimer = window.setTimeout(connect, opened ? RETRY_AFTER_OPEN_MS : RETRY_AFTER_FAIL_MS);
      };
    };
    connect();

    return () => {
      stopped = true;
      window.clearInterval(safety);
      window.clearInterval(beatTimer);
      window.clearTimeout(retryTimer);
      stopPolling();
      socket?.close();
    };
  }, [load]);

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
            {live === "websocket" ? "Live: new activity appears instantly" : live === "polling" ? "Checking for new activity every 10 seconds" : "Connecting…"}
          </p>
        </div>
      )}
    </Popover>
  );
}
