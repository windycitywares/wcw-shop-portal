"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { money } from "../charts/format";
import { DataTable, type Column } from "../ui/DataTable";
import { ConfirmDialog, Modal } from "../ui/Modal";
import { Panel, PanelHeader } from "../ui/Panel";
import { useToast } from "../ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { Schedule, StatusPill, TargetPicker, fromLocalInput, toLocalInput, type Targets } from "./common";

type Kind = "spend_percent" | "spend_fixed" | "qty_percent" | "qty_fixed" | "free_shipping";

interface Offer {
  id: number;
  name: string;
  kind: Kind;
  threshold_amount: number | null;
  threshold_qty: number | null;
  value: number;
  max_discount: number | null;
  scope: "order" | "category" | "products";
  category_ids: number[];
  product_ids: number[];
  exclude_sale_items: boolean;
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
  priority: number;
  translations: Record<string, Record<string, string>>;
  status: string;
}

const KINDS: { id: Kind; label: string }[] = [
  { id: "spend_percent", label: "Spend an amount, get % off" },
  { id: "spend_fixed", label: "Spend an amount, get $ off" },
  { id: "qty_percent", label: "Buy a number of items, get % off" },
  { id: "qty_fixed", label: "Buy a number of items, get $ off" },
  { id: "free_shipping", label: "Spend an amount, get free shipping" },
];

function describe(o: Pick<Offer, "kind" | "value" | "threshold_amount" | "threshold_qty">): string {
  const when = o.kind.startsWith("qty_") ? `buy ${o.threshold_qty}+ items` : `spend ${money(o.threshold_amount ?? 0)}+`;
  const what = o.kind === "free_shipping" ? "free shipping" : o.kind.endsWith("_percent") ? `${o.value}% off` : `${money(o.value)} off`;
  return `${when}, ${what}`;
}

interface Form {
  id?: number;
  name: string;
  name_es: string;
  name_nl: string;
  kind: Kind;
  threshold: string;
  value: string;
  max_discount: string;
  targets: Targets;
  exclude_sale_items: boolean;
  starts: string;
  ends: string;
  is_active: boolean;
}

const EMPTY: Form = {
  name: "",
  name_es: "",
  name_nl: "",
  kind: "spend_percent",
  threshold: "150",
  value: "10",
  max_discount: "",
  targets: { scope: "order", category_ids: [], product_ids: [] },
  exclude_sale_items: false,
  starts: "",
  ends: "",
  is_active: true,
};

export function OffersTab() {
  const { push } = useToast();
  const [rows, setRows] = useState<Offer[] | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [deleting, setDeleting] = useState<Offer | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    apiFetch<Offer[]>("/admin/promotions/offers").then(setRows, (e) => setProblem(e.message));
  }, []);
  useEffect(load, [load]);

  async function save() {
    if (!form) return;
    setBusy(true);
    setProblem("");
    const qty = form.kind.startsWith("qty_");
    const translations: Record<string, Record<string, string>> = {};
    if (form.name_es.trim()) translations.es = { name: form.name_es.trim() };
    if (form.name_nl.trim()) translations.nl = { name: form.name_nl.trim() };
    const body = {
      name: form.name.trim(),
      kind: form.kind,
      threshold_amount: qty ? null : Number(form.threshold),
      threshold_qty: qty ? Number(form.threshold) : null,
      value: form.kind === "free_shipping" ? 0 : Number(form.value),
      max_discount: form.kind.endsWith("_percent") && form.max_discount ? Number(form.max_discount) : null,
      scope: form.targets.scope,
      category_ids: form.targets.category_ids,
      product_ids: form.targets.product_ids,
      exclude_sale_items: form.exclude_sale_items,
      starts_at: fromLocalInput(form.starts),
      ends_at: fromLocalInput(form.ends),
      is_active: form.is_active,
      priority: 0,
      translations,
    };
    try {
      await apiFetch(form.id ? `/admin/promotions/offers/${form.id}` : "/admin/promotions/offers", { method: form.id ? "PUT" : "POST", body: JSON.stringify(body) });
      push({ title: form.id ? "Offer saved" : "Offer created", description: body.name });
      setForm(null);
      load();
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Couldn't save the offer");
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<Offer>[] = [
    {
      key: "name",
      header: "Offer",
      cell: (o) => (
        <div>
          <button
            type="button"
            className="font-medium hover:underline"
            onClick={() => {
              setProblem("");
              setForm({
                id: o.id,
                name: o.name,
                name_es: o.translations?.es?.name ?? "",
                name_nl: o.translations?.nl?.name ?? "",
                kind: o.kind,
                threshold: String(o.kind.startsWith("qty_") ? o.threshold_qty ?? "" : o.threshold_amount ?? ""),
                value: String(o.value),
                max_discount: o.max_discount != null ? String(o.max_discount) : "",
                targets: { scope: o.scope, category_ids: o.category_ids, product_ids: o.product_ids },
                exclude_sale_items: o.exclude_sale_items,
                starts: toLocalInput(o.starts_at),
                ends: toLocalInput(o.ends_at),
                is_active: o.is_active,
              });
            }}
          >
            {o.name}
          </button>
          <span className="block text-xs text-muted">{describe(o)}</span>
        </div>
      ),
    },
    { key: "status", header: "Status", cell: (o) => <StatusPill status={o.status} /> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (o) => (
        <Button size="sm" variant="ghost" className="h-8" onClick={() => setDeleting(o)}>
          Delete
          <span className="sr-only"> {o.name}</span>
        </Button>
      ),
    },
  ];

  const qty = form?.kind.startsWith("qty_");
  return (
    <Panel>
      <PanelHeader
        title="Cart offers"
        description='Applied automatically, no code needed. Shoppers see "add $20 more to get 10% off" in the cart. One offer per order: the best one.'
        actions={
          <Button
            size="sm"
            onClick={() => {
              setProblem("");
              setForm({ ...EMPTY });
            }}
          >
            New offer
          </Button>
        }
      />
      <DataTable columns={columns} rows={rows} rowKey={(o) => o.id} caption="Cart offers" empty='No offers yet. "Spend $150, save 10%" is a good start for raising the average order.' />

      <Modal
        open={!!form}
        onClose={() => setForm(null)}
        title={form?.id ? "Edit offer" : "New offer"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              Cancel
            </Button>
            <Button disabled={busy || !form?.name.trim() || !(Number(form?.threshold) > 0)} onClick={save}>
              {form?.id ? "Save offer" : "Create offer"}
            </Button>
          </>
        }
      >
        {form && (
          <div className="space-y-4">
            {problem && <Alert tone="danger">{problem}</Alert>}
            <Field label="Name shoppers see" hint='E.g. "Spend $150, save 10%".'>
              {(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={120} />}
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Name in Spanish (optional)">{(p) => <Input {...p} value={form.name_es} onChange={(e) => setForm({ ...form, name_es: e.target.value })} maxLength={120} />}</Field>
              <Field label="Name in Dutch (optional)">{(p) => <Input {...p} value={form.name_nl} onChange={(e) => setForm({ ...form, name_nl: e.target.value })} maxLength={120} />}</Field>
            </div>
            <Field label="Type">
              {(p) => (
                <Select {...p} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as Kind })}>
                  {KINDS.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={qty ? "Items needed" : "Amount to spend ($)"}>
                {(p) => <Input {...p} type="number" min={qty ? 2 : 1} step={qty ? 1 : 0.01} value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} />}
              </Field>
              {form.kind !== "free_shipping" && (
                <Field label={form.kind.endsWith("_percent") ? "Percent off" : "Dollars off"}>
                  {(p) => <Input {...p} type="number" min={0.01} step={form.kind.endsWith("_percent") ? 1 : 0.01} value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />}
                </Field>
              )}
            </div>
            {form.kind !== "free_shipping" && <TargetPicker value={form.targets} onChange={(targets) => setForm({ ...form, targets })} everythingScope="order" />}
            <Schedule starts={form.starts} ends={form.ends} onChange={(starts, ends) => setForm({ ...form, starts, ends })} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={form.exclude_sale_items} onChange={(e) => setForm({ ...form, exclude_sale_items: e.target.checked })} />
              Items already on sale don't count
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              Offer is on
            </label>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title={`Delete "${deleting?.name}"?`}
        message="It stops applying to carts straight away. Orders already placed keep their discount."
        confirmLabel="Delete offer"
        tone="danger"
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await apiFetch(`/admin/promotions/offers/${deleting.id}`, { method: "DELETE" });
            push({ title: "Offer deleted", description: deleting.name });
            setDeleting(null);
            load();
          } catch (e) {
            push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
          }
        }}
        onCancel={() => setDeleting(null)}
      />
    </Panel>
  );
}
