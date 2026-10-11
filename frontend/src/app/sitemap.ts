import type { MetadataRoute } from "next";
import { getAllProducts, getCategoryTree } from "@/lib/api";
import { absoluteUrl } from "@/lib/site";
import type { CategoryNode } from "@/lib/types";

export const revalidate = 3600;

function flatten(nodes: CategoryNode[]): CategoryNode[] {
  return nodes.flatMap((n) => [n, ...flatten(n.children)]);
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [tree, products] = await Promise.all([getCategoryTree(), getAllProducts()]);
  return [
    { url: absoluteUrl("/"), changeFrequency: "daily", priority: 1 },
    { url: absoluteUrl("/shop"), changeFrequency: "daily", priority: 0.9 },
    ...flatten(tree).map((c) => ({
      url: absoluteUrl(`/category/${c.slug}`),
      changeFrequency: "weekly" as const,
      priority: 0.7,
    })),
    ...products.map((p) => ({
      url: absoluteUrl(`/product/${p.slug}`),
      lastModified: new Date(p.updated_at),
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
  ];
}
