import type { Metadata } from "next";
import Link from "next/link";
import { isLocale, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { alternates } from "@/lib/seo";
import { ProductListing, type SearchParams } from "@/components/catalog/ProductListing";
import { EmptyState } from "@/components/ui/misc";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = getDictionary(locale);
  return { title: t.deals.title, description: t.deals.description, alternates: alternates(locale, "/deals") };
}

/** Everything that is on sale right now (the API decides what a sale covers). */
export default async function DealsPage({ params, searchParams }: Props) {
  const { locale: raw } = await params;
  const locale: Locale = isLocale(raw) ? raw : "en";
  const t = getDictionary(locale);
  return (
    <ProductListing
      locale={locale}
      title={t.deals.title}
      description={t.deals.description}
      searchParams={await searchParams}
      path="/deals"
      fixedParams={{ on_sale: "true" }}
      breadcrumb={[{ label: t.nav.home, href: localePath(locale, "/") }, { label: t.deals.title }]}
      emptyState={
        <EmptyState title={t.deals.empty}>
          <Link href={localePath(locale, "/shop")} className="underline">
            {t.deals.emptyAction}
          </Link>
        </EmptyState>
      }
    />
  );
}
