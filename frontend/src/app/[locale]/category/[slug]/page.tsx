import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { fmt, isLocale, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getCategory } from "@/lib/api";
import { alternates } from "@/lib/seo";
import { ProductListing, type SearchParams } from "@/components/catalog/ProductListing";
import { JsonLd, breadcrumbLd } from "@/components/seo/JsonLd";
import type { Crumb } from "@/components/ui/misc";

type Props = { params: Promise<{ locale: string; slug: string }>; searchParams: Promise<SearchParams> };

async function load(params: Props["params"]) {
  const { locale: raw, slug } = await params;
  const locale: Locale = isLocale(raw) ? raw : "en";
  return { locale, category: await getCategory(slug, locale) };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, category } = await load(params);
  if (!category) return {};
  const path = `/category/${category.slug}`;
  return {
    title: category.name,
    description: category.description || fmt(getDictionary(locale).meta.categoryDescription, { name: category.name }),
    alternates: alternates(locale, path),
    openGraph: { title: category.name, url: localePath(locale, path) },
  };
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const { locale, category } = await load(params);
  if (!category) notFound();
  const t = getDictionary(locale);

  const crumbs: Crumb[] = [
    { label: t.nav.home, href: localePath(locale, "/") },
    ...category.breadcrumb.map((c) => ({ label: c.name, href: localePath(locale, `/category/${c.slug}`) })),
  ];
  // A theme shows its sibling themes, so visitors can move across them; a parent shows its children.
  let strip = category.children;
  if (strip.length === 0 && category.parent_id) {
    const parent = category.breadcrumb.at(-2);
    const parentDetail = parent ? await getCategory(parent.slug, locale) : null;
    strip = parentDetail?.children ?? [];
  }

  return (
    <>
      <ProductListing
        locale={locale}
        title={category.name}
        description={category.description}
        breadcrumb={crumbs}
        searchParams={await searchParams}
        path={`/category/${category.slug}`}
        categorySlug={category.slug}
        subcategories={strip}
        currentSlug={category.slug}
      />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </>
  );
}
