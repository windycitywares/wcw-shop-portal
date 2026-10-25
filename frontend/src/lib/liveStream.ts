/**
 * Server side of the live updates (Server-Sent Events from this Node server, because the API host can't hold a
 * WebSocket or a streamed response). The stream watches one of the API's cheap `pulse` endpoints for the signed-in
 * person (the browser sends its token in the Authorization header; it is only forwarded to our own API) and writes an
 * event whenever the answer changes. Used by `/api/live/[feed]` and the older `/api/admin-live`.
 */
const API_URL = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
const TICK_MS = 2_000;
const HEARTBEAT_MS = 15_000;
const MAX_LIFETIME_MS = 5 * 60_000; // then the browser reconnects: no stream lives forever

/** The feeds a browser may follow, and the API endpoint each one watches. Nothing else is reachable through here. */
export const LIVE_FEEDS = {
  admin: "/admin/notifications/pulse", // the admin bell (staff)
  account: "/account/notifications/pulse", // the shopper's order bell
} as const;
export type LiveFeed = keyof typeof LIVE_FEEDS;

export function isLiveFeed(value: string): value is LiveFeed {
  return Object.prototype.hasOwnProperty.call(LIVE_FEEDS, value);
}

export function liveStream(request: Request, feed: LiveFeed): Response {
  const auth = request.headers.get("authorization");
  if (!auth?.startsWith("Bearer ")) return new Response("Not signed in", { status: 401 });
  const pulseUrl = `${API_URL}${LIVE_FEEDS[feed]}`;
  const encoder = new TextEncoder();
  let stopped = false;

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (text: string) => {
        if (!stopped) controller.enqueue(encoder.encode(text));
      };
      const stop = () => {
        if (stopped) return;
        stopped = true;
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      };
      request.signal.addEventListener("abort", stop);

      // The padding pushes the first bytes through proxies that wait for a full buffer before forwarding.
      send(`: ${" ".repeat(2048)}\n\nevent: hello\ndata: {}\n\n`);

      const started = Date.now();
      let last = "";
      let lastBeat = Date.now();
      while (!stopped && Date.now() - started < MAX_LIFETIME_MS) {
        try {
          const res = await fetch(pulseUrl, { headers: { Authorization: auth }, cache: "no-store" });
          if (res.status === 401 || res.status === 403) {
            send(`event: signedout\ndata: {}\n\n`);
            break;
          }
          if (res.ok) {
            const pulse = (await res.json()) as { unread: number; latest: string | null };
            const now = `${pulse.unread}|${pulse.latest ?? ""}`;
            if (now !== last) {
              last = now;
              send(`event: pulse\ndata: ${JSON.stringify(pulse)}\n\n`);
            }
          }
        } catch {
          /* the API blinked: try again on the next tick */
        }
        if (Date.now() - lastBeat >= HEARTBEAT_MS) {
          lastBeat = Date.now();
          send(`: ping\n\n`);
        }
        await new Promise((resolve) => setTimeout(resolve, TICK_MS));
      }
      stop();
    },
    cancel() {
      stopped = true;
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      // no-transform keeps compression from holding the stream back; X-Accel-Buffering is honoured by nginx-style proxies.
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
