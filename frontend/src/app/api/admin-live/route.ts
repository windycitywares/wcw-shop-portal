/**
 * Live updates for the admin bell as a stream (Server-Sent Events), because the API host can't hold a WebSocket.
 *
 * This Node server can keep a response open cheaply. It watches the API's /admin/notifications/pulse for the
 * signed-in staff member (the browser sends its token in the Authorization header; it is only forwarded to our API)
 * and writes a line to the open response whenever the answer changes, so the bell hears about a new order within
 * about two seconds. The browser decides whether the stream really arrives live (some proxies buffer a response until it
 * ends); if not it falls back to asking every 10 seconds.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_URL = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
const TICK_MS = 2_000;
const HEARTBEAT_MS = 15_000;
const MAX_LIFETIME_MS = 5 * 60_000; // then the browser reconnects: no stream lives forever

type Pulse = { unread: number; latest: string | null };

export async function GET(request: Request) {
  const auth = request.headers.get("authorization");
  if (!auth?.startsWith("Bearer ")) return new Response("Not signed in", { status: 401 });

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
          const res = await fetch(`${API_URL}/admin/notifications/pulse`, { headers: { Authorization: auth }, cache: "no-store" });
          if (res.status === 401 || res.status === 403) {
            send(`event: signedout\ndata: {}\n\n`);
            break;
          }
          if (res.ok) {
            const pulse = (await res.json()) as Pulse;
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
