import { isLiveFeed, liveStream } from "@/lib/liveStream";

/** Live updates for a bell: /api/live/admin (staff) or /api/live/account (the shopper's orders). See lib/liveStream. */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request, { params }: { params: Promise<{ feed: string }> }) {
  const { feed } = await params;
  if (!isLiveFeed(feed)) return new Response("Not found", { status: 404 });
  return liveStream(request, feed);
}
