"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/client-api";
import { fmtInt, money } from "@/components/admin/charts/format";
import { loadSuppliers, type SupplierRow } from "@/components/admin/SupplierSelect";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

type Draft = { id?: number; name: string; contact_name: string; email: string; phone: string; notes: string; is_active: boolean };
const blank: Draft = { name: "", contact_name: "", email: "", phone: "", notes: "", is_active: true };
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

/** External shops → Suppliers: who you buy from, for every marketplace. Listings, orders and supplier logins pick from here. */
export default function SuppliersPage() {
  const { push } = useToast();
  const [rows, setRows] = useState<SupplierRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    loadSuppliers(true).then((r) => { setRows(r); setError(null); }, (e) => setError(errorText(e)));
  }, []);
  useEffect(load, [load]);

  const save = async () => {
    if (!draft) return;
    setBusy(true);
    const body = { name: draft.name, contact_name: draft.contact_name || null, email: draft.email || null, phone: draft.phone || null, notes: draft.notes || null, is_active: draft.is_active };
    try {
      if (draft.id) await apiFetch(`/admin/suppliers/${draft.id}`, { method: "PATCH", body: JSON.stringify(body) });
      else await apiFetch("/admin/suppliers", { method: "POST", body: JSON.stringify(body) });
      push({ title: draft.id ? "Supplier saved" : "Supplier added", description: draft.name });
      setDraft(null);
      load();
    } catch (e) {
      push({ title: "Not saved", description: errorText(e), tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<SupplierRow>[] = [
    {
      key: "n",
      header: "Supplier",
      cell: (s) => (
        <button type="button" className="text-left font-medium text-accent hover:underline" onClick={() => setDraft({ id: s.id, name: s.name, contact_name: s.contact_name ?? "", email: s.email ?? "", phone: s.phone ?? "", notes: s.notes ?? "", is_active: s.is_active })}>
          {s.name}
          <span className="block text-xs font-normal text-muted">{[s.contact_name, s.email, s.phone].filter(Boolean).join(" · ") || "No contact details"}</span>
        </button>
      ),
    },
    { key: "l", header: "Listings", align: "right", hide: "sm", cell: (s) => fmtInt(s.listings) },
    { key: "o", header: "Open orders", align: "right", cell: (s) => fmtInt(s.open_orders) },
    { key: "w", header: "Owed", align: "right", cell: (s) => <span className={Number(s.owed) ? "font-semibold" : "text-muted"}>{money(Number(s.owed), { cents: true })}</span> },
    { key: "g", header: "Login", hide: "md", cell: (s) => (s.logins ? <Pill tone="success">Has a login</Pill> : <span className="text-muted">—</span>) },
    { key: "a", header: "Status", cell: (s) => <Pill tone={s.is_active ? "success" : "neutral"}>{s.is_active ? "Active" : "Off"}</Pill> },
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader
        title="Suppliers"
        description="Who you buy from, for every marketplace. Listings, orders and supplier logins pick a supplier from this list."
        actions={<Button onClick={() => setDraft({ ...blank })}>Add supplier</Button>}
      />
      {error ? <Alert tone="danger">{error}</Alert> : null}
      <Panel>
        <DataTable columns={columns} rows={rows} rowKey={(s) => s.id} caption="Suppliers" empty="No suppliers yet. Add the first one." />
      </Panel>
      <p className="text-sm text-muted">
        Give a supplier their own login under <Link href="/admin/team" className="underline">Team → Supplier logins</Link>. What you owe each one is under External shops → Etsy → Supplier payments.
      </p>

      <Modal
        open={!!draft}
        onClose={() => setDraft(null)}
        title={draft?.id ? draft.name || "Supplier" : "Add supplier"}
        description={draft?.id ? "Renaming updates the supplier on its listings, orders and login." : undefined}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
            <Button onClick={save} disabled={busy || !draft?.name.trim()}>{busy ? "Saving…" : draft?.id ? "Save supplier" : "Add supplier"}</Button>
          </>
        }
      >
        {draft ? (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2"><Field label="Name">{(p) => <Input {...p} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} maxLength={200} required />}</Field></div>
            <Field label="Contact person">{(p) => <Input {...p} value={draft.contact_name} onChange={(e) => setDraft({ ...draft, contact_name: e.target.value })} maxLength={200} />}</Field>
            <Field label="Phone">{(p) => <Input {...p} type="tel" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} maxLength={50} />}</Field>
            <div className="sm:col-span-2"><Field label="Email">{(p) => <Input {...p} type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />}</Field></div>
            <div className="sm:col-span-2"><Field label="Notes">{(p) => <Textarea {...p} rows={3} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} maxLength={5000} />}</Field></div>
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />
              Active (can be picked on listings and orders)
            </label>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
