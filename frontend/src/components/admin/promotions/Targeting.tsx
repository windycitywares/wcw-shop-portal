"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { DiscountScope, Page, Product } from "@/lib/types";
import { useCategoryTree } from "@/components/admin/useCategoryOptions";
import { Icon } from "@/components/admin/ui/Icon";
import { Field, Input, Select } from "@/components/ui/Field";

export interface ProductPick {
  id: number;
  title: string;
}

export interface TargetState {
  scope: DiscountScope;
  category_id: string;
  products: ProductPick[];
}

export const EMPTY_TARGET: TargetState = { scope: "all", category_id: "", products: [] };

/** What the API wants for "which products does this apply to". */
export function targetPayload(t: TargetState) {
  return {
    scope: t.scope,
    category_id: t.scope === "category" && t.category_id ? Number(t.category_id) : null,
    product_ids: t.scope === "products" ? t.products.map((p) => p.id) : [],
  };
}

/** Product titles for ids we only know by number (when editing something saved earlier). */
export async function pickProducts(ids: number[]): Promise<ProductPick[]> {
  const found = await Promise.all(
    ids.slice(0, 40).map((id) =>
      apiFetch<Product>(`/products/${id}`).then(
        (p) => ({ id, title: p.title }),
        () => ({ id, title: `Product ${id}` }),
      ),
    ),
  );
  return [...found, ...ids.slice(40).map((id) => ({ id, title: `Product ${id}` }))];
}

const SCOPE_LABEL: Record<DiscountScope, string> = { all: "Everything in the shop", category: "One category", products: "Chosen products" };

/** Everything / one category / chosen products. Shared by sales and coupons. */
export function Targeting({ value, onChange }: { value: TargetState; onChange: (t: TargetState) => void }) {
  const { options } = useCategoryTree();
  return (
    <div className="space-y-3">
      <Field label="Applies to">
        {(p) => (
          <Select {...p} value={value.scope} onChange={(e) => onChange({ ...value, scope: e.target.value as DiscountScope })}>
            {(Object.keys(SCOPE_LABEL) as DiscountScope[]).map((s) => (
              <option key={s} value={s}>
                {SCOPE_LABEL[s]}
              </option>
            ))}
          </Select>
        )}
      </Field>
      {value.scope === "category" && (
        <Field label="Category" hint="Includes the categories inside it.">
          {(p) => (
            <Select {...p} required value={value.category_id} onChange={(e) => onChange({ ...value, category_id: e.target.value })}>
              <option value="">Choose a category…</option>
              {options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      {value.scope === "products" && <ProductPicker value={value.products} onChange={(products) => onChange({ ...value, products })} />}
    </div>
  );
}

function ProductPicker({ value, onChange }: { value: ProductPick[]; onChange: (p: ProductPick[]) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      apiFetch<Page<Product>>(`/products?q=${encodeURIComponent(q.trim())}&page_size=8&status=published`, { signal: controller.signal }).then(
        (r) => setResults(r.items),
        () => undefined,
      );
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [q]);
  const chosen = new Set(value.map((p) => p.id));
  const options = results.filter((p) => !chosen.has(p.id));
  return (
    <div>
      <Field label="Find products" hint="Type at least two letters of a title or SKU.">
        {(p) => <Input {...p} type="search" value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off" />}
      </Field>
      {options.length > 0 && (
        <ul className="mt-2 divide-y divide-line rounded-[var(--radius-control)] border border-line bg-surface text-sm" aria-label="Matching products">
          {options.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-sand"
                onClick={() => {
                  onChange([...value, { id: p.id, title: p.title }]);
                  setQ("");
                }}
              >
                <span className="truncate">{p.title}</span>
                <Icon name="plus" className="size-4 text-muted" />
                <span className="sr-only">Add</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {value.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Chosen products">
          {value.map((p) => (
            <li key={p.id} className="inline-flex max-w-full items-center gap-1 rounded-full bg-sand py-1 pl-3 pr-1 text-xs">
              <span className="truncate">{p.title}</span>
              <button
                type="button"
                className="grid size-5 shrink-0 place-items-center rounded-full hover:bg-line"
                onClick={() => onChange(value.filter((x) => x.id !== p.id))}
              >
                <Icon name="close" className="size-3" />
                <span className="sr-only">Remove {p.title}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
