"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { CategoryNode } from "@/lib/types";

export interface CategoryOption {
  id: number;
  label: string; // "Home › Decor › Vases"
  node: CategoryNode;
}

export function flattenTree(nodes: CategoryNode[], trail: string[] = []): CategoryOption[] {
  return nodes.flatMap((n) => {
    const path = [...trail, n.name];
    return [{ id: n.id, label: path.join(" › "), node: n }, ...flattenTree(n.children, path)];
  });
}

export function useCategoryTree() {
  const [tree, setTree] = useState<CategoryNode[]>([]);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    apiFetch<CategoryNode[]>("/categories/tree?include_inactive=true").then(setTree, () => setTree([]));
  }, [version]);
  return { tree, options: flattenTree(tree), reload: () => setVersion((v) => v + 1) };
}
