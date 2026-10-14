"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { ShippingMethod } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { Panel, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Form {
  code: string;
  name: string;
  description: string;
  price: string;
  free_over: string;
  min_days: string;
  max_days: string;
  countries: string;
  is_active: boolean;
  sort_order: string;
}

const EMPTY: Form = { code: "", name: "", description: "", price: "", free_over: "", min_days: "", max_days: "", countries: "", is_active: true, sort_order: "0" };

const toForm = (m: ShippingMethod): Form => ({
  code: m.code,
  name: m.name,
  description: m.description ?? "",
  price: String(m.price),
  free_over: m.free_over != null ? String(m.free_over) : "",
  min_days: m.min_days != null ? String(m.min_days) : "",
  max_days: m.max_days != null ? String(m.max_days) : "",
  countries: m.countries.join(", "),
  is_active: m.is_active,
  sort_order: String(m.sort_order),
});

const optionalNumber = (v: string) => (v.trim() === "" ? null : Number(v));

function body(f: Form) {
  return {
    code: f.code.trim(),
    name: f.name.trim(),
    description: f.description.trim() || null,
    price: Number(f.price || 0),
    free_over: optionalNumber(f.free_over),
    min_days: optionalNumber(f.min_days),
    max_days: optionalNumber(f.max_days),
    countries: f.countries.split(/[\s,;]+/).filter(Boolean),
    is_active: f.is_active,
    sort_order: Number(f.sort_order || 0),
  };
}

export function ShippingPanel() {
  const { push } = useToast();
  const [methods, setMethods] = useState<ShippingMethod[] | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<ShippingMethod | "new" | null>(null);
  const [deleting, setDeleting] = useState<ShippingMethod | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setMethods(await apiFetch<ShippingMethod[]>("/settings/shipping"));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load shipping methods");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function remove(m: ShippingMethod) {
    setBusy(true);
    try {
      await apiFetch(`/settings/shipping/${m.id}`, { method: "DELETE" });
      push({ title: "Shipping method deleted", description: m.name });
      setDeleting(null);
      await load();
    } catch (e) {
      setDeleting(null);
      setError(e instanceof Error ? e.message : "That didn't work");
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<ShippingMethod>[] = [
    {
      key: "name",
      header: "Method",
      cell: (m) => (
        <div className="min-w-0">
          <p className="font-medium">{m.name}</p>
          <p className="text-xs text-muted">
            {m.min_days != null && m.max_days != null ? `${m.min_days}–${m.max_days} business days` : m.max_days != null ? `Up to ${m.max_days} business days` : "No delivery estimate"}
          </p>
        </div>
      ),
    },
    { key: "price", header: "Price", align: "right", cell: (m) => <span className="num">{formatPrice(m.price, "USD")}</span> },
    { key: "free", header: "Free over", align: "right", hide: "sm", cell: (m) => <span className="num text-muted">{m.free_over != null ? formatPrice(m.free_over, "USD") : "—"}</span> },
    { key: "where", header: "Ships to", hide: "md", cell: (m) => <span className="text-muted">{m.countries.length > 0 ? m.countries.join(", ") : "Everywhere"}</span> },
    { key: "status", header: "Status", cell: (m) => <Pill tone={m.is_active ? "success" : "neutral"}>{m.is_active ? "On" : "Off"}</Pill> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (m) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" className="h-8" onClick={() => setEditing(m)}>
            Edit<span className="sr-only"> {m.name}</span>
          </Button>
          <Button size="sm" variant="ghost" className="h-8 text-danger" onClick={() => setDeleting(m)}>
            Delete<span className="sr-only"> {m.name}</span>
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Panel>
      <PanelHeader
        title="Shipping methods"
        description="What customers can choose at checkout. Check these prices: they started as examples."
        actions={
          <Button size="sm" className="h-9" onClick={() => setEditing("new")}>
            <Icon name="plus" className="size-4" />
            Add method
          </Button>
        }
      />
      {error && (
        <Alert tone="danger" className="m-4">
          {error}
        </Alert>
      )}
      <DataTable caption="Shipping methods" columns={columns} rows={methods} rowKey={(m) => m.id} empty="No shipping methods yet. Checkout needs at least one." />

      <ShippingForm
        method={editing}
        onClose={() => setEditing(null)}
        onSaved={async (message) => {
          setEditing(null);
          push({ title: message });
          await load();
        }}
      />
      <ConfirmDialog
        open={deleting != null}
        title="Delete this shipping method?"
        message="Customers won't be able to choose it any more. You can switch it off instead."
        confirmLabel="Delete method"
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && remove(deleting)}
      />
    </Panel>
  );
}

function ShippingForm({ method, onClose, onSaved }: { method: ShippingMethod | "new" | null; onClose: () => void; onSaved: (message: string) => void | Promise<void> }) {
  const isNew = method === "new";
  const [form, setForm] = useState<Form>(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (method == null) return;
    setForm(method === "new" ? EMPTY : toForm(method));
    setError("");
    setBusy(false);
  }, [method]);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (method == null) return;
    setBusy(true);
    setError("");
    try {
      if (method === "new") {
        await apiFetch("/settings/shipping", { method: "POST", body: JSON.stringify(body(form)) });
        await onSaved("Shipping method added");
      } else {
        await apiFetch(`/settings/shipping/${method.id}`, { method: "PUT", body: JSON.stringify(body(form)) });
        await onSaved("Shipping method saved");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
      setBusy(false);
    }
  }

  return (
    <Modal
      open={method != null}
      onClose={onClose}
      size="lg"
      title={isNew ? "Add a shipping method" : "Edit shipping method"}
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="shipping-form" size="sm" className="h-9" disabled={busy}>
            {busy ? "Saving…" : isNew ? "Add method" : "Save changes"}
          </Button>
        </>
      }
    >
      <form id="shipping-form" onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" hint="What customers see, e.g. Standard shipping.">
            {(p) => <Input {...p} value={form.name} onChange={(e) => set("name", e.target.value)} required maxLength={100} />}
          </Field>
          <Field label="Short code" hint="Lowercase letters, numbers, dashes. Used inside the system.">
            {(p) => <Input {...p} value={form.code} onChange={(e) => set("code", e.target.value.toLowerCase())} required pattern="[a-z0-9][a-z0-9_\-]{1,39}" maxLength={40} className="font-mono" readOnly={!isNew} />}
          </Field>
        </div>
        <Field label="Description (optional)">{(p) => <Input {...p} value={form.description} onChange={(e) => set("description", e.target.value)} maxLength={300} />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Price (USD)">
            {(p) => <Input {...p} type="number" inputMode="decimal" step="0.01" min="0" required value={form.price} onChange={(e) => set("price", e.target.value)} />}
          </Field>
          <Field label="Free when the order is over (optional)" hint="After discounts. Empty = never free.">
            {(p) => <Input {...p} type="number" inputMode="decimal" step="0.01" min="0.01" value={form.free_over} onChange={(e) => set("free_over", e.target.value)} />}
          </Field>
          <Field label="Fastest delivery (business days)">
            {(p) => <Input {...p} type="number" inputMode="numeric" step="1" min="0" max="365" value={form.min_days} onChange={(e) => set("min_days", e.target.value)} />}
          </Field>
          <Field label="Slowest delivery (business days)">
            {(p) => <Input {...p} type="number" inputMode="numeric" step="1" min="0" max="365" value={form.max_days} onChange={(e) => set("max_days", e.target.value)} />}
          </Field>
        </div>
        <Field label="Countries (optional)" hint="Two-letter codes separated by commas, e.g. US, CA. Empty = everywhere.">
          {(p) => <Input {...p} value={form.countries} onChange={(e) => set("countries", e.target.value.toUpperCase())} className="font-mono" autoComplete="off" />}
        </Field>
        <div className="grid items-end gap-4 sm:grid-cols-2">
          <Field label="Order in the list" hint="Smaller numbers come first.">
            {(p) => <Input {...p} type="number" inputMode="numeric" step="1" min="0" max="1000" value={form.sort_order} onChange={(e) => set("sort_order", e.target.value)} />}
          </Field>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
            Customers can choose this
          </label>
        </div>
      </form>
    </Modal>
  );
}
