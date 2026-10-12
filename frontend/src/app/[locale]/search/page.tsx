import type { Metadata } from "next";
import { fmt, isLocale, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { ProductListing, type SearchParams } from "@/components/catalog/ProductListing";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  return {
    title: isLocale(locale) ? getDictionary(locale).listing.searchTitle : "Search",
    robots: { index: false, follow: true },
  };
}

export default async function SearchPage({ params, searchParams }: Props) {
  const { locale: raw } = await params;
  const locale: Locale = isLocale(raw) ? raw : "en";
  const t = getDictionary(locale);
  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q.trim() : "";
  return (
    <ProductListing
      locale={locale}
      title={q ? fmt(t.listing.resultsFor, { q }) : t.listing.searchTitle}
      searchParams={sp}
      path="/search"
      breadcrumb={[{ label: t.nav.home, href: localePath(locale, "/") }, { label: t.listing.searchTitle }]}
    />
  );
}
