import type { MetadataRoute } from "next";
import { localePath, locales } from "@/i18n/config";
import { getAllProducts, getCategoryTree } from "@/lib/api";
import { absoluteUrl } from "@/lib/site";
import type { CategoryNode } from "@/lib/types";

export const revalidate = 3600;

function flatten(nodes: CategoryNode[]): CategoryNode[] {
  return nodes.flatMap((n) => [n, ...flatten(n.children)]);
}

/** One entry per page in English, with its Spanish and Dutch versions as hreflang alternates. */
function entry(path: string, extra: Omit<MetadataRoute.Sitemap[number], "url">): MetadataRoute.Sitemap[number] {
  return {
    url: absoluteUrl(path),
    alternates: { languages: Object.fromEntries(locales.map((l) => [l, absoluteUrl(localePath(l, path))])) },
    ...extra,
  };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [tree, products] = await Promise.all([getCategoryTree(), getAllProducts()]);
  return [
    entry("/", { changeFrequency: "daily", priority: 1 }),
    entry("/shop", { changeFrequency: "daily", priority: 0.9 }),
    entry("/deals", { changeFrequency: "daily", priority: 0.7 }),
    entry("/contact", { changeFrequency: "yearly", priority: 0.3 }),
    ...flatten(tree).map((c) => entry(`/category/${c.slug}`, { changeFrequency: "weekly", priority: 0.7 })),
    ...products.map((p) =>
      entry(`/product/${p.slug}`, { lastModified: new Date(p.updated_at), changeFrequency: "weekly", priority: 0.8 }),
    ),
  ];
}
