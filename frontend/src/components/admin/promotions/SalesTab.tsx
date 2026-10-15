"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { money } from "../charts/format";
import { DataTable, type Column } from "../ui/DataTable";
import { ConfirmDialog, Modal } from "../ui/Modal";
import { Panel, PanelHeader } from "../ui/Panel";
import { useToast } from "../ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { Schedule, StatusPill, TargetPicker, fromLocalInput, shortDate, toLocalInput, type Targets } from "./common";

export interface Sale {
  id: number;
  name: string;
  badge: string | null;
  description: string | null;
  kind: "percent" | "fixed";
  value: number;
  scope: "all" | "category" | "products";
  category_ids: number[];
  product_ids: number[];
  exclude_product_ids: number[];
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
  translations: Record<string, Record<string, string>>;
  status: string;
  affected_products: number;
}

interface Form {
  id?: number;
  name: string;
  badge: string;
  description: string;
  kind: "percent" | "fixed";
  value: string;
  targets: Targets;
  starts: string;
  ends: string;
  badge_es: string;
  badge_nl: string;
}

const EMPTY: Form = {
  name: "",
  badge: "",
  description: "",
  kind: "percent",
  value: "20",
  targets: { scope: "all", category_ids: [], product_ids: [] },
  starts: "",
  ends: "",
  badge_es: "",
  badge_nl: "",
};

export function SalesTab() {
  const { push } = useToast();
  const [rows, setRows] = useState<Sale[] | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [deleting, setDeleting] = useState<Sale | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    apiFetch<Sale[]>("/admin/promotions/sales").then(setRows, (e) => setProblem(e.message));
  }, []);
  useEffect(load, [load]);

  function edit(s: Sale) {
    setProblem("");
    setForm({
      id: s.id,
      name: s.name,
      badge: s.badge ?? "",
      description: s.description ?? "",
      kind: s.kind,
      value: String(s.value),
      targets: { scope: s.scope, category_ids: s.category_ids, product_ids: s.product_ids },
      starts: toLocalInput(s.starts_at),
      ends: toLocalInput(s.ends_at),
      badge_es: s.translations?.es?.badge ?? "",
      badge_nl: s.translations?.nl?.badge ?? "",
    });
  }

  async function save() {
    if (!form) return;
    setBusy(true);
    setProblem("");
    const translations: Record<string, Record<string, string>> = {};
    if (form.badge_es.trim()) translations.es = { badge: form.badge_es.trim() };
    if (form.badge_nl.trim()) translations.nl = { badge: form.badge_nl.trim() };
    const body = {
      name: form.name.trim(),
      badge: form.badge.trim() || null,
      description: form.description.trim() || null,
      kind: form.kind,
      value: Number(form.value),
      scope: form.targets.scope,
      category_ids: form.targets.category_ids,
      product_ids: form.targets.product_ids,
      starts_at: fromLocalInput(form.starts),
      ends_at: fromLocalInput(form.ends),
      is_active: true,
      translations,
    };
    try {
      await apiFetch(form.id ? `/admin/promotions/sales/${form.id}` : "/admin/promotions/sales", {
        method: form.id ? "PUT" : "POST",
        body: JSON.stringify(body),
      });
      push({ title: form.id ? "Sale saved" : "Sale created", description: body.name });
      setForm(null);
      load();
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Couldn't save the sale");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(s: Sale) {
    try {
      await apiFetch(`/admin/promotions/sales/${s.id}/active`, { method: "POST", body: JSON.stringify({ is_active: !s.is_active }) });
      push({ title: s.is_active ? "Sale paused" : "Sale resumed", description: s.name });
      load();
    } catch (e) {
      push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    }
  }

  const columns: Column<Sale>[] = [
    {
      key: "name",
      header: "Sale",
      cell: (s) => (
        <div>
          <button type="button" className="font-medium hover:underline" onClick={() => edit(s)}>
            {s.name}
          </button>
          <span className="block text-xs text-muted">
            {s.kind === "percent" ? `${s.value}% off` : `${money(s.value)} off`} ·{" "}
            {s.scope === "all" ? "every product" : s.scope === "category" ? `${s.category_ids.length} categories` : `${s.product_ids.length} products`} ·{" "}
            {s.affected_products} on sale
          </span>
        </div>
      ),
    },
    {
      key: "when",
      header: "When",
      hide: "md",
      cell: (s) => (
        <span className="text-sm text-muted">
          {s.starts_at ? shortDate(s.starts_at) : "Now"} – {s.ends_at ? shortDate(s.ends_at) : "until paused"}
        </span>
      ),
    },
    { key: "status", header: "Status", cell: (s) => <StatusPill status={s.status} /> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (s) => (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="secondary" className="h-8" onClick={() => toggle(s)}>
            {s.is_active ? "Pause" : "Resume"}
            <span className="sr-only"> {s.name}</span>
          </Button>
          <Button size="sm" variant="ghost" className="h-8" onClick={() => setDeleting(s)}>
            Delete
            <span className="sr-only"> {s.name}</span>
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Panel>
      <PanelHeader
        title="Sales"
        description="Lower prices on the shop for a while. Shoppers see the sale price and badge everywhere; the best sale wins."
        actions={
          <Button
            size="sm"
            onClick={() => {
              setProblem("");
              setForm({ ...EMPTY });
            }}
          >
            New sale
          </Button>
        }
      />
      <DataTable columns={columns} rows={rows} rowKey={(s) => s.id} caption="Sales" empty="No sales yet. Create one to show sale prices and a badge in the shop." />

      <Modal
        open={!!form}
        onClose={() => setForm(null)}
        title={form?.id ? "Edit sale" : "New sale"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              Cancel
            </Button>
            <Button disabled={busy || !form?.name.trim() || !(Number(form?.value) > 0)} onClick={save}>
              {form?.id ? "Save sale" : "Create sale"}
            </Button>
          </>
        }
      >
        {form && (
          <div className="space-y-4">
            {problem && <Alert tone="danger">{problem}</Alert>}
            <Field label="Name" hint="For you, e.g. Fall sale 2026.">
              {(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={120} />}
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Discount type">
                {(p) => (
                  <Select {...p} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as Form["kind"] })}>
                    <option value="percent">Percentage off</option>
                    <option value="fixed">Amount off each item</option>
                  </Select>
                )}
              </Field>
              <Field label={form.kind === "percent" ? "Percent off" : "Dollars off"} error={form.kind === "percent" && Number(form.value) >= 100 ? "Less than 100%" : undefined}>
                {(p) => <Input {...p} type="number" min={0.01} step={form.kind === "percent" ? 1 : 0.01} value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />}
              </Field>
            </div>
            <TargetPicker value={form.targets} onChange={(targets) => setForm({ ...form, targets })} everythingScope="all" />
            <Schedule starts={form.starts} ends={form.ends} onChange={(starts, ends) => setForm({ ...form, starts, ends })} />
            <Field label="Badge on products (optional)" hint='Short, e.g. "Fall sale". Empty: shows the percentage.'>
              {(p) => <Input {...p} value={form.badge} onChange={(e) => setForm({ ...form, badge: e.target.value })} maxLength={40} />}
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Badge in Spanish (optional)">{(p) => <Input {...p} value={form.badge_es} onChange={(e) => setForm({ ...form, badge_es: e.target.value })} maxLength={40} />}</Field>
              <Field label="Badge in Dutch (optional)">{(p) => <Input {...p} value={form.badge_nl} onChange={(e) => setForm({ ...form, badge_nl: e.target.value })} maxLength={40} />}</Field>
            </div>
            <Field label="Notes (optional)" hint="Only for you.">
              {(p) => <Textarea {...p} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={1000} className="min-h-20" />}
            </Field>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title={`Delete "${deleting?.name}"?`}
        message="Prices go back to normal straight away. Orders already placed keep their sale prices."
        confirmLabel="Delete sale"
        tone="danger"
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await apiFetch(`/admin/promotions/sales/${deleting.id}`, { method: "DELETE" });
            push({ title: "Sale deleted", description: deleting.name });
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
