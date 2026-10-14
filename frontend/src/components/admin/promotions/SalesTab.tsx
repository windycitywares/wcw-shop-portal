"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { Sale } from "@/lib/types";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { SALE_STATUS_LABEL, SALE_STATUS_TONE, day, describeDiscount, saleBody } from "./format";
import { fromLocalInput, toLocalInput } from "./RulesFields";
import { EMPTY_TARGET, Targeting, pickProducts, targetPayload, type TargetState } from "./Targeting";

export function SalesTab() {
  const { push } = useToast();
  const [sales, setSales] = useState<Sale[] | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Sale | "new" | null>(null);
  const [deleting, setDeleting] = useState<Sale | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setSales(await apiFetch<Sale[]>("/promotions/sales"));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load sales");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function setActive(s: Sale, is_active: boolean) {
    try {
      await apiFetch(`/promotions/sales/${s.id}`, { method: "PUT", body: JSON.stringify(saleBody(s, { is_active })) });
      push({ title: is_active ? "Sale resumed" : "Sale paused", description: s.name });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work");
    }
  }

  async function remove(s: Sale) {
    setBusy(true);
    try {
      await apiFetch(`/promotions/sales/${s.id}`, { method: "DELETE" });
      push({ title: "Sale deleted", description: s.name });
      setDeleting(null);
      await load();
    } catch (e) {
      setDeleting(null);
      setError(e instanceof Error ? e.message : "That didn't work");
    } finally {
      setBusy(false);
    }
  }

  const appliesTo = (s: Sale) =>
    s.scope === "all" ? "Everything" : s.scope === "category" ? (s.category_name ?? "One category") : s.products.length > 0 ? s.products.slice(0, 2).join(", ") + (s.products.length > 2 ? ` and ${s.products.length - 2} more` : "") : "Chosen products";

  const columns: Column<Sale>[] = [
    {
      key: "name",
      header: "Sale",
      cell: (s) => (
        <div className="min-w-0">
          <p className="font-medium">{s.name}</p>
          {s.label && <p className="text-xs text-muted">Badge: {s.label}</p>}
        </div>
      ),
    },
    { key: "discount", header: "Discount", cell: (s) => <span className="font-medium">{describeDiscount(s.kind, s.value)}</span> },
    { key: "scope", header: "Applies to", hide: "sm", cell: (s) => <span className="text-muted">{appliesTo(s)}</span> },
    {
      key: "when",
      header: "When",
      hide: "md",
      cell: (s) => (
        <span className="text-muted">
          {s.starts_at ? day(s.starts_at) : "Now"} – {s.ends_at ? day(s.ends_at) : "no end date"}
        </span>
      ),
    },
    { key: "status", header: "Status", cell: (s) => <Pill tone={SALE_STATUS_TONE[s.status]}>{SALE_STATUS_LABEL[s.status]}</Pill> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (s) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" className="h-8" onClick={() => setEditing(s)}>
            Edit<span className="sr-only"> {s.name}</span>
          </Button>
          <Button size="sm" variant="ghost" className="h-8" onClick={() => setActive(s, !s.is_active)}>
            {s.is_active ? "Pause" : "Resume"}
            <span className="sr-only"> {s.name}</span>
          </Button>
          <Button size="sm" variant="ghost" className="h-8 text-danger" onClick={() => setDeleting(s)}>
            Delete<span className="sr-only"> {s.name}</span>
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <p className="max-w-xl text-sm text-muted">A sale lowers prices for everyone, with no code needed. Shoppers see the old price crossed out and a badge on the product.</p>
          <Button size="sm" className="h-9" onClick={() => setEditing("new")}>
            <Icon name="plus" className="size-4" />
            New sale
          </Button>
        </div>
        <DataTable caption="Sales" columns={columns} rows={sales} rowKey={(s) => s.id} empty="No sales yet. A seasonal sale on one category is a good first one." />
      </Panel>

      <SaleForm
        sale={editing}
        onClose={() => setEditing(null)}
        onSaved={async (message) => {
          setEditing(null);
          push({ title: message });
          await load();
        }}
      />
      <ConfirmDialog
        open={deleting != null}
        title="Delete this sale?"
        message={<>Prices go back to normal straight away. You can pause a sale instead and bring it back later.</>}
        confirmLabel="Delete sale"
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && remove(deleting)}
      />
    </div>
  );
}

function SaleForm({ sale, onClose, onSaved }: { sale: Sale | "new" | null; onClose: () => void; onSaved: (message: string) => void | Promise<void> }) {
  const isNew = sale === "new";
  const [name, setName] = useState("");
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<"percent" | "fixed">("percent");
  const [value, setValue] = useState("15");
  const [target, setTarget] = useState<TargetState>(EMPTY_TARGET);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [active, setActive] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (sale == null) return;
    setError("");
    setBusy(false);
    if (sale === "new") {
      setName("");
      setLabel("");
      setKind("percent");
      setValue("15");
      setTarget(EMPTY_TARGET);
      setStartsAt("");
      setEndsAt("");
      setActive(true);
      setReady(true);
      return;
    }
    let live = true;
    setReady(false);
    void (sale.scope === "products" ? pickProducts(sale.product_ids) : Promise.resolve([])).then((products) => {
      if (!live) return;
      setName(sale.name);
      setLabel(sale.label ?? "");
      setKind(sale.kind);
      setValue(String(sale.value));
      setTarget({ scope: sale.scope, category_id: sale.category_id != null ? String(sale.category_id) : "", products });
      setStartsAt(toLocalInput(sale.starts_at));
      setEndsAt(toLocalInput(sale.ends_at));
      setActive(sale.is_active);
      setReady(true);
    });
    return () => {
      live = false;
    };
  }, [sale]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (sale == null) return;
    setBusy(true);
    setError("");
    const body = {
      ...targetPayload(target),
      name: name.trim(),
      label: label.trim() || null,
      kind,
      value: Number(value),
      starts_at: fromLocalInput(startsAt),
      ends_at: fromLocalInput(endsAt),
      is_active: active,
    };
    try {
      if (sale === "new") {
        await apiFetch("/promotions/sales", { method: "POST", body: JSON.stringify(body) });
        await onSaved("Sale created");
      } else {
        await apiFetch(`/promotions/sales/${sale.id}`, { method: "PUT", body: JSON.stringify(body) });
        await onSaved("Sale saved");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the sale");
      setBusy(false);
    }
  }

  return (
    <Modal
      open={sale != null}
      onClose={onClose}
      size="lg"
      title={isNew ? "New sale" : "Edit sale"}
      description="Prices drop for everyone while the sale runs. When products are in more than one sale, the best price wins."
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="sale-form" size="sm" className="h-9" disabled={busy || !ready}>
            {busy ? "Saving…" : isNew ? "Create sale" : "Save changes"}
          </Button>
        </>
      }
    >
      {!ready ? (
        <div className="skeleton h-40 w-full" aria-label="Loading" />
      ) : (
        <form id="sale-form" onSubmit={submit} className="space-y-5">
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" hint="For your team, e.g. Fall keepsake sale.">
              {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />}
            </Field>
            <Field label="Badge on the product (optional)" hint="A short word shoppers see, e.g. Autumn sale.">
              {(p) => <Input {...p} value={label} onChange={(e) => setLabel(e.target.value)} maxLength={40} />}
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Discount">
              {(p) => (
                <Select {...p} value={kind} onChange={(e) => setKind(e.target.value as "percent" | "fixed")}>
                  <option value="percent">Percent off</option>
                  <option value="fixed">Amount off each item</option>
                </Select>
              )}
            </Field>
            <Field label={kind === "percent" ? "Percent (1–100)" : "Amount off (USD)"}>
              {(p) => (
                <Input {...p} type="number" inputMode="decimal" required step={kind === "percent" ? "0.5" : "0.01"} min="0.01" max={kind === "percent" ? "100" : undefined} value={value} onChange={(e) => setValue(e.target.value)} />
              )}
            </Field>
          </div>
          <Targeting value={target} onChange={setTarget} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Starts (optional)" hint="Empty = starts now.">
              {(p) => <Input {...p} type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />}
            </Field>
            <Field label="Ends (optional)" hint="Empty = runs until you stop it.">
              {(p) => <Input {...p} type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />}
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
            Sale is switched on
          </label>
        </form>
      )}
    </Modal>
  );
}
