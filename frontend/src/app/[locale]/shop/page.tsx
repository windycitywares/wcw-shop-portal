import type { Metadata } from "next";
import { isLocale, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getCategoryTree } from "@/lib/api";
import { alternates } from "@/lib/seo";
import { ProductListing, type SearchParams } from "@/components/catalog/ProductListing";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = getDictionary(locale);
  return { title: t.nav.shopAll, description: t.meta.shopAllDescription, alternates: alternates(locale, "/shop") };
}

export default async function ShopPage({ params, searchParams }: Props) {
  const { locale: raw } = await params;
  const locale: Locale = isLocale(raw) ? raw : "en";
  const t = getDictionary(locale);
  const tree = await getCategoryTree(locale);
  const themes = tree.length === 1 ? tree[0].children : tree;
  return (
    <ProductListing
      locale={locale}
      title={t.nav.shopAll}
      description={t.meta.tagline}
      searchParams={await searchParams}
      path="/shop"
      subcategories={themes}
      breadcrumb={[{ label: t.nav.home, href: localePath(locale, "/") }, { label: t.nav.shopAll }]}
    />
  );
}
