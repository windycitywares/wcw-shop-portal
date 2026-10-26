"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch, tokenStore } from "@/lib/client-api";
import { useToast } from "../ui/Toast";

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
const MUTE_KEY = "wcw-live-muted";
/** These pop up in the corner; everything else updates the bell and the pages quietly. */
const TOAST_KINDS = new Set(["order.new", "message.new", "backup.failed"]);
const SOUND_KINDS = new Set(["order.new"]);

const Ctx = createContext<{
  mode: LiveMode;
  muted: boolean;
  setMuted: (m: boolean) => void;
  subscribe: (l: Listener) => () => void;
} | null>(null);

function chime() {
  try {
    const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return;
    const ctx = new AC();
    [880, 1320].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = freq;
      osc.connect(gain);
      gain.connect(ctx.destination);
      const t = ctx.currentTime + i * 0.16;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.15, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.25);
      osc.start(t);
      osc.stop(t + 0.3);
    });
    window.setTimeout(() => void ctx.close(), 1000);
  } catch {
    /* no sound is fine */
  }
}

export function LiveProvider({ children }: { children: React.ReactNode }) {
  const { push } = useToast();
  const { user } = useAuth();
  const meRef = useRef<number | null>(null);
  meRef.current = user?.id ?? null;
  const [mode, setMode] = useState<LiveMode>("connecting");
  const [muted, setMutedState] = useState(false);
  const listeners = useRef(new Set<Listener>());
  const mutedRef = useRef(false);
  const pushRef = useRef(push);
  pushRef.current = push;

  useEffect(() => {
    try {
      const m = localStorage.getItem(MUTE_KEY) === "1";
      mutedRef.current = m;
      setMutedState(m);
    } catch {
      /* storage unavailable */
    }
  }, []);
  const setMuted = useCallback((m: boolean) => {
    mutedRef.current = m;
    setMutedState(m);
    try {
      localStorage.setItem(MUTE_KEY, m ? "1" : "0");
    } catch {
      /* storage unavailable */
    }
  }, []);

  const subscribe = useCallback((l: Listener) => {
    listeners.current.add(l);
    return () => void listeners.current.delete(l);
  }, []);

  useEffect(() => {
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
      const loud = events.filter((e) => TOAST_KINDS.has(e.kind));
      if (loud.length > 2) {
        pushRef.current({ tone: "info", title: `${loud.length} new updates`, description: loud.map((e) => e.title).slice(0, 3).join(" · "), href: "/admin/notifications", action: "See all" });
      } else {
        for (const e of loud) {
          pushRef.current({ tone: e.kind === "backup.failed" ? "danger" : "info", title: e.title, description: e.detail ?? undefined, href: e.href ?? undefined, action: "View" });
        }
      }
      // One sound per browser: only the leader plays it, even when its tab is in the background.
      if (leader && !mutedRef.current && events.some((e) => SOUND_KINDS.has(e.kind))) chime();
    };
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
        const data = msg.data as { type: string; batch?: Batch; mode?: LiveMode };
        if (data.type === "batch" && data.batch) {
          lastId = data.batch.last_id;
          deliver(data.batch.events, false);
        } else if (data.type === "mode" && data.mode) setMode(data.mode);
        else if (data.type === "ask" && leading) channel.postMessage({ type: "mode", mode: currentMode });
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
    const startPolling = () => {
      if (stopped) return;
      announceMode("polling");
      if (pollTimer === undefined) {
        void poll();
        pollTimer = window.setInterval(() => void poll(), PULSE_MS);
      }
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
              if (lastId === null) lastId = (JSON.parse(data) as { last_id: number }).last_id;
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
      stopPolling();
      abort?.abort();
      channel?.close();
    };
  }, []);

  const value = useMemo(() => ({ mode, muted, setMuted, subscribe }), [mode, muted, setMuted, subscribe]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLiveStatus() {
  const ctx = useContext(Ctx);
  return { mode: ctx?.mode ?? "off", muted: ctx?.muted ?? false, setMuted: ctx?.setMuted ?? (() => undefined) };
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
