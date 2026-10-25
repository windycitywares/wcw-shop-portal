"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch, tokenStore } from "@/lib/client-api";

const PULSE_MS = 10_000; // without a live stream: ask "anything new?" this often
const FIRST_BYTES_MS = 5_000; // a stream that says nothing by now is being held back by the host
const RETRY_AFTER_LIVE_MS = 5_000; // a stream that worked and ended: reconnect soon
const RETRY_AFTER_FAIL_MS = 120_000; // a stream that never arrived live: don't keep knocking

export type Pulse = { unread: number; latest: string | null };
/** How the page hears about news: a live stream from the storefront server, or by asking every few seconds. */
export type LiveMode = "off" | "connecting" | "stream" | "polling";

const signature = (p: Pulse) => `${p.unread}|${p.latest ?? ""}`;

/**
 * Calls `onChange` whenever the given feed has news (a new order, a status change, something read in another tab).
 * Tries the live stream (`/api/live/<feed>`, about two seconds) and falls back to asking the API's `pulse` every
 * 10 seconds. The stream is read with fetch, not EventSource, so the token travels in a header, not in the address.
 */
export function useLiveSignal(feed: "admin" | "account", pulsePath: string, enabled: boolean, onChange: () => void): LiveMode {
  const [mode, setMode] = useState<LiveMode>(enabled ? "connecting" : "off");
  const callback = useRef(onChange);
  callback.current = onChange;

  useEffect(() => {
    if (!enabled) {
      setMode("off");
      return;
    }
    let stopped = false;
    let last = "";
    let abort: AbortController | null = null;
    let pollTimer: number | undefined;
    let retryTimer: number | undefined;

    const changed = (p: Pulse) => {
      const now = signature(p);
      if (now !== last) {
        const first = last === "";
        last = now;
        if (!first) callback.current(); // the page loaded its own data already; only real news reloads it
      }
    };
    const poll = () => {
      if (document.visibilityState !== "visible") return;
      apiFetch<Pulse>(pulsePath).then(changed, () => undefined);
    };
    const startPolling = () => {
      if (stopped) return;
      setMode("polling");
      if (pollTimer === undefined) {
        poll();
        pollTimer = window.setInterval(poll, PULSE_MS);
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
        const res = await fetch(`/api/live/${feed}`, { headers: { Authorization: `Bearer ${token}` }, signal: ctl.signal, cache: "no-store" });
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
            if (event === "hello") {
              arrived = true;
              window.clearTimeout(giveUp);
              stopPolling();
              setMode("stream");
            } else if (event === "pulse" && data) {
              changed(JSON.parse(data) as Pulse);
            } else if (event === "signedout") {
              window.clearTimeout(giveUp);
              return startPolling(); // the page's own requests take the person to sign in
            }
          }
        }
      } catch {
        /* aborted, offline or not supported: handled below */
      }
      window.clearTimeout(giveUp);
      if (stopped) return;
      startPolling(); // never without news: ask every few seconds until the stream is back
      retryTimer = window.setTimeout(() => void connect(), arrived ? RETRY_AFTER_LIVE_MS : RETRY_AFTER_FAIL_MS);
    };
    void connect();

    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      stopPolling();
      abort?.abort();
    };
  }, [feed, pulsePath, enabled]);

  return mode;
}
