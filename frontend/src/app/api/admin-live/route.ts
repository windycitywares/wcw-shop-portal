import { liveStream } from "@/lib/liveStream";

/** Kept for admin tabs opened before /api/live/admin existed; same stream. */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  return liveStream(request, "admin");
}
