import type { Metadata } from "next";
import { ProductListing, type SearchParams } from "@/components/catalog/ProductListing";

export const metadata: Metadata = {
  title: "Search",
  robots: { index: false, follow: true },
};

export default async function SearchPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q.trim() : "";
  return (
    <ProductListing
      title={q ? `Results for “${q}”` : "Search"}
      searchParams={params}
      basePath="/search"
      breadcrumb={[{ label: "Home", href: "/" }, { label: "Search" }]}
    />
  );
}
