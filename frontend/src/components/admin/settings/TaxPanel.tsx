"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { TaxRate } from "@/lib/types";
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
  name: string;
  country: string;
  region: string;
  rate: string;
  applies_to_shipping: boolean;
  is_active: boolean;
}

const EMPTY: Form = { name: "", country: "US", region: "", rate: "", applies_to_shipping: false, is_active: true };

export function TaxPanel() {
  const { push } = useToast();
  const [rates, setRates] = useState<TaxRate[] | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<TaxRate | "new" | null>(null);
  const [deleting, setDeleting] = useState<TaxRate | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRates(await apiFetch<TaxRate[]>("/settings/tax"));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tax rates");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function remove(r: TaxRate) {
    setBusy(true);
    try {
      await apiFetch(`/settings/tax/${r.id}`, { method: "DELETE" });
      push({ title: "Tax rate deleted", description: r.name });
      setDeleting(null);
      await load();
    } catch (e) {
      setDeleting(null);
      setError(e instanceof Error ? e.message : "That didn't work");
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<TaxRate>[] = [
    { key: "name", header: "Name", cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: "where", header: "Where", cell: (r) => <span className="text-muted">{r.region ? `${r.region}, ${r.country}` : `All of ${r.country}`}</span> },
    { key: "rate", header: "Rate", align: "right", cell: (r) => <span className="num">{r.rate}%</span> },
    { key: "ship", header: "On shipping too", hide: "sm", cell: (r) => <span className="text-muted">{r.applies_to_shipping ? "Yes" : "No"}</span> },
    { key: "status", header: "Status", cell: (r) => <Pill tone={r.is_active ? "success" : "neutral"}>{r.is_active ? "On" : "Off"}</Pill> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" className="h-8" onClick={() => setEditing(r)}>
            Edit<span className="sr-only"> {r.name}</span>
          </Button>
          <Button size="sm" variant="ghost" className="h-8 text-danger" onClick={() => setDeleting(r)}>
            Delete<span className="sr-only"> {r.name}</span>
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Panel>
      <PanelHeader
        title="Sales tax"
        description="Added at checkout where a rate matches the delivery address. Ask your accountant which places you must collect in."
        actions={
          <Button size="sm" className="h-9" onClick={() => setEditing("new")}>
            <Icon name="plus" className="size-4" />
            Add rate
          </Button>
        }
      />
      {error && (
        <Alert tone="danger" className="m-4">
          {error}
        </Alert>
      )}
      <DataTable caption="Tax rates" columns={columns} rows={rates} rowKey={(r) => r.id} empty="No tax rates. Orders are charged no tax until you add one." />

      <TaxForm
        rate={editing}
        onClose={() => setEditing(null)}
        onSaved={async (message) => {
          setEditing(null);
          push({ title: message });
          await load();
        }}
      />
      <ConfirmDialog
        open={deleting != null}
        title="Delete this tax rate?"
        message="New orders won't be charged this tax. Orders already placed keep what they were charged."
        confirmLabel="Delete rate"
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && remove(deleting)}
      />
    </Panel>
  );
}

function TaxForm({ rate, onClose, onSaved }: { rate: TaxRate | "new" | null; onClose: () => void; onSaved: (message: string) => void | Promise<void> }) {
  const isNew = rate === "new";
  const [form, setForm] = useState<Form>(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (rate == null) return;
    setForm(
      rate === "new"
        ? EMPTY
        : { name: rate.name, country: rate.country, region: rate.region ?? "", rate: String(rate.rate), applies_to_shipping: rate.applies_to_shipping, is_active: rate.is_active },
    );
    setError("");
    setBusy(false);
  }, [rate]);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (rate == null) return;
    setBusy(true);
    setError("");
    const payload = {
      name: form.name.trim(),
      country: form.country.trim().toUpperCase(),
      region: form.region.trim() || null,
      rate: Number(form.rate),
      applies_to_shipping: form.applies_to_shipping,
      is_active: form.is_active,
    };
    try {
      if (rate === "new") {
        await apiFetch("/settings/tax", { method: "POST", body: JSON.stringify(payload) });
        await onSaved("Tax rate added");
      } else {
        await apiFetch(`/settings/tax/${rate.id}`, { method: "PUT", body: JSON.stringify(payload) });
        await onSaved("Tax rate saved");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
      setBusy(false);
    }
  }

  return (
    <Modal
      open={rate != null}
      onClose={onClose}
      title={isNew ? "Add a tax rate" : "Edit tax rate"}
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="tax-form" size="sm" className="h-9" disabled={busy}>
            {busy ? "Saving…" : isNew ? "Add rate" : "Save changes"}
          </Button>
        </>
      }
    >
      <form id="tax-form" onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Name" hint="Shown on the receipt, e.g. Illinois sales tax.">
          {(p) => <Input {...p} value={form.name} onChange={(e) => set("name", e.target.value)} required maxLength={100} />}
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Country" hint="Two letters, e.g. US.">
            {(p) => <Input {...p} value={form.country} onChange={(e) => set("country", e.target.value.toUpperCase())} required pattern="[A-Za-z]{2}" maxLength={2} className="font-mono uppercase" />}
          </Field>
          <Field label="State (optional)" hint="Empty = the whole country.">
            {(p) => <Input {...p} value={form.region} onChange={(e) => set("region", e.target.value)} maxLength={100} />}
          </Field>
          <Field label="Rate (%)">
            {(p) => <Input {...p} type="number" inputMode="decimal" step="0.001" min="0" max="100" required value={form.rate} onChange={(e) => set("rate", e.target.value)} />}
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.applies_to_shipping} onChange={(e) => set("applies_to_shipping", e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
          Also charge it on shipping
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
          Rate is switched on
        </label>
      </form>
    </Modal>
  );
}
