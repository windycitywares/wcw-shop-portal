import { NextResponse, type NextRequest } from "next/server";
import { LOCALE_COOKIE, defaultLocale, isLocale, matchAcceptLanguage } from "@/i18n/config";

/**
 * Language routing (Next.js "proxy", formerly middleware):
 * - /es/... and /nl/... are served as they are.
 * - /en/... redirects to the bare path (English has no prefix).
 * - Bare paths: a saved choice (cookie) wins, otherwise the browser's Accept-Language;
 *   Spanish/Dutch visitors are redirected to their prefix, everyone else gets English
 *   (served internally from /en/...).
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const first = pathname.split("/")[1];

  if (first === "es" || first === "nl") return NextResponse.next();

  if (first === "en") {
    const url = request.nextUrl.clone();
    url.pathname = pathname.slice(3) || "/";
    return NextResponse.redirect(url, 308);
  }

  const saved = request.cookies.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(saved) ? saved : matchAcceptLanguage(request.headers.get("accept-language"));

  if (locale !== defaultLocale) {
    const url = request.nextUrl.clone();
    url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
    url.search = search;
    const res = NextResponse.redirect(url, 307);
    res.headers.set("Vary", "Accept-Language, Cookie");
    return res;
  }

  const url = request.nextUrl.clone();
  url.pathname = pathname === "/" ? "/en" : `/en${pathname}`;
  const res = NextResponse.rewrite(url);
  res.headers.set("Vary", "Accept-Language, Cookie");
  return res;
}

export const config = {
  // Everything except Next internals, the admin, metadata routes and files with an extension
  matcher: ["/((?!_next|admin|api|robots\\.txt|sitemap\\.xml|icon\\.svg|favicon\\.ico|.*\\.[\\w]+$).*)"],
};
