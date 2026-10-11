import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getCategory } from "@/lib/api";
import { site } from "@/lib/site";
import { ProductListing, type SearchParams } from "@/components/catalog/ProductListing";
import { JsonLd, breadcrumbLd } from "@/components/seo/JsonLd";
import type { Crumb } from "@/components/ui/misc";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const category = await getCategory(slug);
  if (!category) return { title: "Category not found" };
  return {
    title: category.name,
    description: category.description || `Shop ${category.name} at ${site.name}.`,
    alternates: { canonical: `/category/${category.slug}` },
    openGraph: { title: category.name, url: `/category/${category.slug}` },
  };
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const category = await getCategory(slug);
  if (!category) notFound();

  const crumbs: Crumb[] = [
    { label: "Home", href: "/" },
    ...category.breadcrumb.map((c) => ({ label: c.name, href: `/category/${c.slug}` })),
  ];

  return (
    <>
      <ProductListing
        title={category.name}
        description={category.description}
        breadcrumb={crumbs}
        searchParams={await searchParams}
        basePath={`/category/${category.slug}`}
        categorySlug={category.slug}
        subcategories={category.children}
      />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </>
  );
}
