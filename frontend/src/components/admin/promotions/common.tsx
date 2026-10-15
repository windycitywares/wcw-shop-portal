"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { CategoryNode, Page, Product } from "@/lib/types";
import { Pill, type Tone } from "../ui/Pill";
import { Field, Input, Select } from "@/components/ui/Field";

/** "2026-10-20T14:00:00Z" → "2026-10-20T09:00" for <input type="datetime-local"> (browser's time zone). */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromLocalInput(v: string): string | null {
  return v ? new Date(v).toISOString() : null;
}

export function shortDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "";
}

const STATUS: Record<string, { label: string; tone: Tone }> = {
  active: { label: "Running", tone: "success" },
  scheduled: { label: "Scheduled", tone: "info" },
  ended: { label: "Ended", tone: "neutral" },
  expired: { label: "Expired", tone: "neutral" },
  paused: { label: "Paused", tone: "warning" },
  used_up: { label: "Used up", tone: "neutral" },
};

export function StatusPill({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: "neutral" as const };
  return <Pill tone={s.tone}>{s.label}</Pill>;
}

export type Scope = "all" | "order" | "category" | "products";

export interface Targets {
  scope: Scope;
  category_ids: number[];
  product_ids: number[];
}

function flatten(nodes: CategoryNode[], depth = 0): { id: number; name: string; depth: number }[] {
  return nodes.flatMap((n) => [{ id: n.id, name: n.name, depth }, ...flatten(n.children, depth + 1)]);
}

/** Who a sale, coupon or offer applies to: everything, some categories (with their sub-categories) or chosen products. */
export function TargetPicker({
  value,
  onChange,
  everythingScope,
}: {
  value: Targets;
  onChange: (t: Targets) => void;
  /** Sales say "all", coupons and offers say "order" for "the whole order". */
  everythingScope: "all" | "order";
}) {
  const [categories, setCategories] = useState<{ id: number; name: string; depth: number }[]>([]);
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Product[]>([]);
  const [chosen, setChosen] = useState<Record<number, string>>({});

  useEffect(() => {
    apiFetch<CategoryNode[]>("/categories/tree").then((t) => setCategories(flatten(t)), () => setCategories([]));
  }, []);

  // Show names for products already chosen (editing an existing promotion).
  useEffect(() => {
    const missing = value.product_ids.filter((id) => !chosen[id]);
    if (!missing.length) return;
    Promise.all(missing.slice(0, 50).map((id) => apiFetch<Product>(`/products/by-id/${id}`).catch(() => null))).then((list) =>
      setChosen((c) => ({ ...c, ...Object.fromEntries(list.filter(Boolean).map((p) => [p!.id, p!.title])) })),
    );
  }, [value.product_ids, chosen]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setFound([]);
      return;
    }
    const timer = setTimeout(() => {
      apiFetch<Page<Product>>(`/products?q=${encodeURIComponent(q.trim())}&page_size=8&status=published`).then((r) => setFound(r.items), () => setFound([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <div className="space-y-3">
      <Field label="Applies to">
        {(p) => (
          <Select {...p} value={value.scope} onChange={(e) => onChange({ ...value, scope: e.target.value as Scope })}>
            <option value={everythingScope}>{everythingScope === "all" ? "Every product" : "The whole order"}</option>
            <option value="category">Some categories</option>
            <option value="products">Chosen products</option>
          </Select>
        )}
      </Field>
      {value.scope === "category" && (
        <fieldset className="max-h-56 overflow-y-auto rounded-lg border border-line p-3">
          <legend className="px-1 text-sm font-medium">Categories (sub-categories included)</legend>
          {categories.map((c) => (
            <label key={c.id} className="flex items-center gap-2 py-1 text-sm" style={{ paddingLeft: c.depth * 16 }}>
              <input
                type="checkbox"
                className="size-4 accent-[var(--color-accent)]"
                checked={value.category_ids.includes(c.id)}
                onChange={(e) =>
                  onChange({
                    ...value,
                    category_ids: e.target.checked ? [...value.category_ids, c.id] : value.category_ids.filter((x) => x !== c.id),
                  })
                }
              />
              {c.name}
            </label>
          ))}
        </fieldset>
      )}
      {value.scope === "products" && (
        <div className="space-y-2">
          <Field label="Find products">
            {(p) => <Input {...p} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type at least two letters" />}
          </Field>
          {found.length > 0 && (
            <ul className="divide-y divide-line rounded-lg border border-line text-sm">
              {found.map((p) => {
                const on = value.product_ids.includes(p.id);
                return (
                  <li key={p.id} className="flex items-center justify-between gap-3 px-3 py-2">
                    <span className="truncate">{p.title}</span>
                    <button
                      type="button"
                      className="shrink-0 text-accent underline underline-offset-4"
                      onClick={() => {
                        setChosen((c) => ({ ...c, [p.id]: p.title }));
                        onChange({ ...value, product_ids: on ? value.product_ids.filter((x) => x !== p.id) : [...value.product_ids, p.id] });
                      }}
                    >
                      {on ? "Remove" : "Add"}
                      <span className="sr-only"> {p.title}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {value.product_ids.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="Chosen products">
              {value.product_ids.map((id) => (
                <li key={id} className="inline-flex items-center gap-1 rounded-full bg-sand px-3 py-1 text-xs">
                  {chosen[id] ?? `#${id}`}
                  <button type="button" aria-label={`Remove ${chosen[id] ?? id}`} className="ml-1" onClick={() => onChange({ ...value, product_ids: value.product_ids.filter((x) => x !== id) })}>
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/** Start/end pair. Empty start = now; empty end = until stopped. */
export function Schedule({
  starts,
  ends,
  onChange,
  endLabel = "Ends",
}: {
  starts: string;
  ends: string;
  onChange: (starts: string, ends: string) => void;
  endLabel?: string;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label="Starts (optional)" hint="Empty: straight away.">
        {(p) => <Input {...p} type="datetime-local" value={starts} onChange={(e) => onChange(e.target.value, ends)} />}
      </Field>
      <Field label={`${endLabel} (optional)`} hint="Empty: until you pause it." error={starts && ends && ends <= starts ? "Must be after the start" : undefined}>
        {(p) => <Input {...p} type="datetime-local" value={ends} onChange={(e) => onChange(starts, e.target.value)} />}
      </Field>
    </div>
  );
}
