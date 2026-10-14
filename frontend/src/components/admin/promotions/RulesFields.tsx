"use client";

import type { Coupon, CouponKind } from "@/lib/types";
import { Field, Input, Select } from "@/components/ui/Field";
import { EMPTY_TARGET, Targeting, pickProducts, targetPayload, type TargetState } from "./Targeting";

/** The discount rules shared by a single coupon, a batch of codes and a personal code. */
export interface RulesState {
  description: string;
  kind: CouponKind;
  value: string;
  min_subtotal: string;
  max_discount: string;
  target: TargetState;
  exclude_sale_items: boolean;
  first_order_only: boolean;
  per_customer_limit: string;
  starts_at: string;
  expires_at: string;
}

export const EMPTY_RULES: RulesState = {
  description: "",
  kind: "percent",
  value: "10",
  min_subtotal: "",
  max_discount: "",
  target: EMPTY_TARGET,
  exclude_sale_items: false,
  first_order_only: false,
  per_customer_limit: "",
  starts_at: "",
  expires_at: "",
};

const pad = (n: number) => String(n).padStart(2, "0");

/** ISO time from the API -> the "2026-10-14T09:30" a datetime-local field wants (in the browser's time zone). */
export function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** The reverse: a datetime-local value -> ISO (UTC) for the API. */
export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export async function rulesFromCoupon(c: Coupon): Promise<RulesState> {
  return {
    description: c.description ?? "",
    kind: c.kind,
    value: c.kind === "free_shipping" ? "" : String(c.value),
    min_subtotal: c.min_subtotal != null ? String(c.min_subtotal) : "",
    max_discount: c.max_discount != null ? String(c.max_discount) : "",
    target: {
      scope: c.scope,
      category_id: c.category_id != null ? String(c.category_id) : "",
      products: c.scope === "products" ? await pickProducts(c.product_ids) : [],
    },
    exclude_sale_items: c.exclude_sale_items,
    first_order_only: c.first_order_only,
    per_customer_limit: c.per_customer_limit != null ? String(c.per_customer_limit) : "",
    starts_at: toLocalInput(c.starts_at),
    expires_at: toLocalInput(c.expires_at),
  };
}

const num = (v: string) => (v.trim() === "" ? null : Number(v));

/** The part of the request body that describes the discount. */
export function rulesPayload(r: RulesState) {
  return {
    ...targetPayload(r.target),
    description: r.description.trim() || null,
    kind: r.kind,
    value: r.kind === "free_shipping" ? 0 : Number(r.value || 0),
    min_subtotal: num(r.min_subtotal),
    max_discount: r.kind === "percent" ? num(r.max_discount) : null,
    exclude_sale_items: r.exclude_sale_items,
    first_order_only: r.first_order_only,
    per_customer_limit: num(r.per_customer_limit),
    starts_at: fromLocalInput(r.starts_at),
    expires_at: fromLocalInput(r.expires_at),
  };
}

const KIND_LABEL: Record<CouponKind, string> = { percent: "Percent off", fixed: "Amount off", free_shipping: "Free shipping" };

export function RulesFields({ value, onChange }: { value: RulesState; onChange: (r: RulesState) => void }) {
  const set = <K extends keyof RulesState>(key: K, v: RulesState[K]) => onChange({ ...value, [key]: v });
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Discount">
          {(p) => (
            <Select {...p} value={value.kind} onChange={(e) => set("kind", e.target.value as CouponKind)}>
              {(Object.keys(KIND_LABEL) as CouponKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {value.kind !== "free_shipping" && (
          <Field label={value.kind === "percent" ? "Percent (1–100)" : "Amount off (USD)"}>
            {(p) => (
              <Input
                {...p}
                type="number"
                inputMode="decimal"
                required
                step={value.kind === "percent" ? "0.5" : "0.01"}
                min="0.01"
                max={value.kind === "percent" ? "100" : undefined}
                value={value.value}
                onChange={(e) => set("value", e.target.value)}
              />
            )}
          </Field>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Minimum spend (optional)" hint="Counted on eligible items, after sales.">
          {(p) => <Input {...p} type="number" inputMode="decimal" step="0.01" min="0.01" value={value.min_subtotal} onChange={(e) => set("min_subtotal", e.target.value)} />}
        </Field>
        {value.kind === "percent" && (
          <Field label="Most it can take off (optional)" hint="A cap, so a big order can't get too large a discount.">
            {(p) => <Input {...p} type="number" inputMode="decimal" step="0.01" min="0.01" value={value.max_discount} onChange={(e) => set("max_discount", e.target.value)} />}
          </Field>
        )}
      </div>
      <Targeting value={value.target} onChange={(t) => set("target", t)} />
      <div className="space-y-2 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={value.exclude_sale_items} onChange={(e) => set("exclude_sale_items", e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
          Don&apos;t apply to items that are already on sale
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={value.first_order_only} onChange={(e) => set("first_order_only", e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
          First order only
        </label>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Each customer can use it (times)" hint="Leave empty for no limit.">
          {(p) => <Input {...p} type="number" inputMode="numeric" step="1" min="1" value={value.per_customer_limit} onChange={(e) => set("per_customer_limit", e.target.value)} />}
        </Field>
        <Field label="Starts (optional)">
          {(p) => <Input {...p} type="datetime-local" value={value.starts_at} onChange={(e) => set("starts_at", e.target.value)} />}
        </Field>
        <Field label="Ends (optional)">
          {(p) => <Input {...p} type="datetime-local" value={value.expires_at} onChange={(e) => set("expires_at", e.target.value)} />}
        </Field>
      </div>
      <Field label="Note for your team (optional)" hint="Only you see this. For example: the flyer this code is printed on.">
        {(p) => <Input {...p} value={value.description} maxLength={300} onChange={(e) => set("description", e.target.value)} />}
      </Field>
    </div>
  );
}
