/** Which build this storefront server runs (the admin compares it with the build a page was loaded with). */
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ version: process.env.NEXT_PUBLIC_BUILD_SHA || "" }, { headers: { "Cache-Control": "no-store" } });
}
