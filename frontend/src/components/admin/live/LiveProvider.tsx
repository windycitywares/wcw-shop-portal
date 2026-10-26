"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch, tokenStore } from "@/lib/client-api";
import { DEFAULT_PREFS, plan, type NotificationPrefs } from "@/lib/liveCategories";
import { useToast } from "../ui/Toast";
import { playSound, unlockSoundOnFirstInteraction } from "./sounds";

/**
 * Live updates in the admin: new orders, payments, messages, sign-ups… as they happen (GET /admin/live/events).
 *
 * One browser keeps one connection however many admin tabs are open: the tab holding the "wcw-live" lock is the
 * leader, reads the stream (`/api/live`, about two seconds) or, if the host holds that back, asks the API every
 * 10 seconds, and passes every batch to the other tabs over a BroadcastChannel. When the leader tab closes, another
 * takes over from the last event seen. Pages subscribe with `useLive(prefixes, callback)`.
 */

export interface LiveEvent {
  id: number;
  kind: string; // order.new, order.paid, order.status, order.refund, customer.new, subscriber.new, message.new …
  ref_id: number | null;
  title: string;
  detail: string | null;
  href: string | null;
  actor_id: number | null; // the signed-in person who made the change (none: a shopper, a job, a payment)
  actor_name: string | null;
  at: string;
}
type Batch = { events: LiveEvent[]; last_id: number };
export type LiveMode = "connecting" | "stream" | "polling" | "off";
type Listener = { prefixes: string[]; fn: (events: LiveEvent[]) => void };

const CHANNEL = "wcw-live";
const LOCK = "wcw-live-leader";
const PULSE_MS = 10_000;
const FIRST_BYTES_MS = 5_000;
const RETRY_AFTER_LIVE_MS = 3_000;
const RETRY_AFTER_FAIL_MS = 120_000;
/** This build's version (baked in by the storefront workflow); the stream says which one the server now runs. */
const MY_VERSION = process.env.NEXT_PUBLIC_BUILD_SHA || "";
const VERSION_CHECK_MS = 60_000;

const Ctx = createContext<{
  mode: LiveMode;
  prefs: NotificationPrefs;
  setPrefs: (p: NotificationPrefs) => void;
  newVersion: boolean;
  subscribe: (l: Listener) => () => void;
} | null>(null);

function desktopAlert(e: LiveEvent) {
  try {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    const n = new Notification(e.title, { body: e.detail ?? undefined, tag: `wcw-live-${e.id}`, icon: "/apple-icon.png" });
    n.onclick = () => {
      window.focus();
      if (e.href) window.location.assign(e.href);
      n.close();
    };
  } catch {
    /* not available here */
  }
}

export function LiveProvider({ children }: { children: React.ReactNode }) {
  const { push } = useToast();
  const { user } = useAuth();
  const meRef = useRef<number | null>(null);
  meRef.current = user?.id ?? null;
  const [mode, setMode] = useState<LiveMode>("connecting");
  const [prefs, setPrefsState] = useState<NotificationPrefs>(DEFAULT_PREFS);
  const [newVersion, setNewVersion] = useState(false);
  const listeners = useRef(new Set<Listener>());
  const prefsRef = useRef<NotificationPrefs>(DEFAULT_PREFS);
  const pushRef = useRef(push);
  pushRef.current = push;

  // Each person's own choices (Admin → Notification settings); the defaults until they arrive.
  const setPrefs = useCallback((p: NotificationPrefs) => {
    prefsRef.current = p;
    setPrefsState(p);
  }, []);
  useEffect(() => {
    const unlock = unlockSoundOnFirstInteraction();
    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    };
  }, []);
  useEffect(() => {
    apiFetch<{ prefs: NotificationPrefs }>("/admin/live/preferences").then((r) => setPrefs(r.prefs), () => undefined);
  }, [setPrefs]);

  const subscribe = useCallback((l: Listener) => {
    listeners.current.add(l);
    return () => void listeners.current.delete(l);
  }, []);

  useEffect(() => {
    // Switched off for this browser (the page-load tests wait for the network to go quiet, which an open stream never does).
    try {
      if (localStorage.getItem("wcw-live") === "off") {
        setMode("off");
        return;
      }
    } catch {
      /* storage unavailable: carry on */
    }
    let stopped = false;
    let leading = false;
    let currentMode: LiveMode = "connecting";
    let lastId: number | null = null;
    const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel(CHANNEL) : null;

    // Every tab: hand the events to the pages that care, and pop up the important ones.
    const deliver = (all: LiveEvent[], leader: boolean) => {
      // What this person did themselves (in this tab or another) isn't news to them.
      const events = all.filter((e) => e.actor_id === null || e.actor_id !== meRef.current);
      if (!events.length) return;
      for (const l of listeners.current) {
        const mine = events.filter((e) => l.prefixes.some((p) => e.kind.startsWith(p)));
        if (mine.length) l.fn(mine);
      }
      const todo = plan(events, prefsRef.current);
      const loud = todo.popups;
      if (loud.length > 2) {
        pushRef.current({ tone: "info", title: `${loud.length} new updates`, description: loud.map((e) => e.title).slice(0, 3).join(" · "), href: "/admin/notifications", action: "See all" });
      } else {
        for (const e of loud) {
          pushRef.current({ tone: e.kind === "backup.failed" ? "danger" : "info", title: e.title, description: e.detail ?? undefined, href: e.href ?? undefined, action: "View" });
        }
      }
      // One sound and one desktop alert per browser: only the leader gives them, even when its tab is in the background.
      if (leader && todo.sound) playSound(prefsRef.current.sound, prefsRef.current.volume);
      if (leader && document.visibilityState !== "visible") todo.desktop.slice(0, 3).forEach(desktopAlert);
    };
    // "A new version is out": the server's build differs from the one this page was loaded with.
    const sawVersion = (version: string, share: boolean) => {
      if (!version || !MY_VERSION || version === MY_VERSION) return;
      setNewVersion(true);
      if (share) channel?.postMessage({ type: "version", version });
    };
    const checkVersion = () =>
      fetch("/api/version", { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((v: { version?: string } | null) => v?.version && sawVersion(v.version, true))
        .catch(() => undefined);
    const announce = (batch: Batch) => {
      lastId = batch.last_id;
      deliver(batch.events, true);
      channel?.postMessage({ type: "batch", batch });
    };
    const announceMode = (m: LiveMode) => {
      currentMode = m;
      setMode(m);
      channel?.postMessage({ type: "mode", mode: m });
    };
    if (channel) {
      channel.onmessage = (msg: MessageEvent) => {
        const data = msg.data as { type: string; batch?: Batch; mode?: LiveMode; version?: string };
        if (data.type === "batch" && data.batch) {
          lastId = data.batch.last_id;
          deliver(data.batch.events, false);
        } else if (data.type === "mode" && data.mode) setMode(data.mode);
        else if (data.type === "ask" && leading) channel.postMessage({ type: "mode", mode: currentMode });
        else if (data.type === "version" && data.version) sawVersion(data.version, false);
      };
      channel.postMessage({ type: "ask" }); // a tab opened later learns how the leader is connected
    }

    // ---- the leader's work ---------------------------------------------------------------------------------
    let pollTimer: number | undefined;
    let retryTimer: number | undefined;
    let abort: AbortController | null = null;
    const poll = async () => {
      try {
        const batch = await apiFetch<Batch>(`/admin/live/events${lastId === null ? "" : `?after=${lastId}`}`);
        if (lastId === null) lastId = batch.last_id;
        else announce(batch);
      } catch {
        /* try again next time */
      }
    };
    let versionTimer: number | undefined;
    const startPolling = () => {
      if (stopped) return;
      announceMode("polling");
      if (pollTimer === undefined) {
        void poll();
        pollTimer = window.setInterval(() => void poll(), PULSE_MS);
      }
      if (versionTimer === undefined) versionTimer = window.setInterval(() => void checkVersion(), VERSION_CHECK_MS);
    };
    const stopPolling = () => {
      window.clearInterval(pollTimer);
      pollTimer = undefined;
    };
    const connect = async () => {
      const token = tokenStore.get();
      if (stopped || !token) return startPolling();
      const ctl = new AbortController();
      abort = ctl;
      let arrived = false;
      const giveUp = window.setTimeout(() => !arrived && ctl.abort(), FIRST_BYTES_MS);
      try {
        const res = await fetch(`/api/live${lastId === null ? "" : `?after=${lastId}`}`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: ctl.signal,
          cache: "no-store",
        });
        if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let end: number;
          while ((end = buffer.indexOf("\n\n")) >= 0) {
            const block = buffer.slice(0, end);
            buffer = buffer.slice(end + 2);
            const event = /^event: (.+)$/m.exec(block)?.[1];
            const data = /^data: (.+)$/m.exec(block)?.[1];
            if (event === "hello" && data) {
              arrived = true;
              window.clearTimeout(giveUp);
              stopPolling();
              const hello = JSON.parse(data) as { last_id: number; version?: string };
              if (lastId === null) lastId = hello.last_id;
              if (hello.version) sawVersion(hello.version, true);
              announceMode("stream");
            } else if (event === "events" && data) {
              announce(JSON.parse(data) as Batch);
            } else if (event === "signedout") {
              window.clearTimeout(giveUp);
              return startPolling();
            }
          }
        }
      } catch {
        /* aborted, offline or held back: handled below */
      }
      window.clearTimeout(giveUp);
      if (stopped) return;
      startPolling(); // never without news: ask every 10 seconds until the stream is back
      retryTimer = window.setTimeout(() => void connect(), arrived ? RETRY_AFTER_LIVE_MS : RETRY_AFTER_FAIL_MS);
    };
    const lead = () =>
      new Promise<void>((release) => {
        leading = true;
        void connect();
        const check = window.setInterval(() => {
          if (stopped) {
            window.clearInterval(check);
            release();
          }
        }, 500);
      });

    // Only one tab per browser leads; the others listen. Without Web Locks every tab leads on its own.
    const locks = typeof navigator !== "undefined" ? (navigator as Navigator & { locks?: LockManager }).locks : undefined;
    if (locks && channel) {
      void locks.request(LOCK, () => (stopped ? Promise.resolve() : lead())).catch(() => undefined);
    } else {
      void lead();
    }

    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      window.clearInterval(versionTimer);
      stopPolling();
      abort?.abort();
      channel?.close();
    };
  }, []);

  const value = useMemo(() => ({ mode, prefs, setPrefs, newVersion, subscribe }), [mode, prefs, setPrefs, newVersion, subscribe]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLiveStatus() {
  const ctx = useContext(Ctx);
  return {
    mode: ctx?.mode ?? "off",
    prefs: ctx?.prefs ?? DEFAULT_PREFS,
    setPrefs: ctx?.setPrefs ?? (() => undefined),
    newVersion: ctx?.newVersion ?? false,
  };
}

/** Calls `fn` with the events whose kind starts with one of `prefixes` ("order.", "message.new" …). */
export function useLive(prefixes: string[], fn: (events: LiveEvent[]) => void) {
  const ctx = useContext(Ctx);
  const callback = useRef(fn);
  callback.current = fn;
  const key = prefixes.join("|");
  useEffect(() => {
    if (!ctx) return;
    return ctx.subscribe({ prefixes: key.split("|"), fn: (e) => callback.current(e) });
  }, [ctx, key]);
}
