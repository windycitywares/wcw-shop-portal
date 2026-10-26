/**
 * Live updates for the admin, as a stream (Server-Sent Events). The API host can only answer ordinary requests, but this
 * Node server can keep a response open: it asks the API's GET /admin/live/events?after=N every two seconds on behalf of
 * the signed-in staff member (their token arrives in the Authorization header and only goes to our own API) and writes
 * what's new to the open response. The browser falls back to asking the API itself every 10 seconds if this is held back.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_URL = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
const TICK_MS = 2_000;
const HEARTBEAT_MS = 15_000;
const MAX_LIFETIME_MS = 5 * 60_000; // then the browser reconnects (from the last id it saw): no stream lives forever

type Batch = { events: unknown[]; last_id: number };

export async function GET(request: Request) {
  const auth = request.headers.get("authorization");
  if (!auth?.startsWith("Bearer ")) return new Response("Not signed in", { status: 401 });
  const requested = Number(new URL(request.url).searchParams.get("after"));
  let after: number | null = Number.isFinite(requested) && requested > 0 ? requested : null;
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
      send(`: ${" ".repeat(2048)}\n\n`);

      const started = Date.now();
      let lastBeat = Date.now();
      let greeted = false;
      while (!stopped && Date.now() - started < MAX_LIFETIME_MS) {
        try {
          const url = `${API_URL}/admin/live/events${after === null ? "" : `?after=${after}`}`;
          const res = await fetch(url, { headers: { Authorization: auth }, cache: "no-store" });
          if (res.status === 401 || res.status === 403) {
            send(`event: signedout\ndata: {}\n\n`);
            break;
          }
          if (res.ok) {
            const batch = (await res.json()) as Batch;
            if (!greeted) {
              greeted = true;
              const version = process.env.NEXT_PUBLIC_BUILD_SHA || "";
              send(`event: hello\ndata: ${JSON.stringify({ last_id: after ?? batch.last_id, version })}\n\n`);
            }
            if (batch.events.length) send(`event: events\ndata: ${JSON.stringify(batch)}\n\n`);
            after = batch.last_id;
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
