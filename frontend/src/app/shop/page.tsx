import type { Metadata } from "next";
import { ProductListing, type SearchParams } from "@/components/catalog/ProductListing";

export const metadata: Metadata = {
  title: "Shop all",
  description: "Browse the full Windy City Wares collection.",
  alternates: { canonical: "/shop" },
};

export default async function ShopPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  return (
    <ProductListing
      title="Shop all"
      searchParams={await searchParams}
      basePath="/shop"
      breadcrumb={[{ label: "Home", href: "/" }, { label: "Shop all" }]}
    />
  );
}
