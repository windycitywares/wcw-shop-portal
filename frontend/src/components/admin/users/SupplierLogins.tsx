"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { User } from "@/lib/types";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Modal } from "@/components/admin/ui/Modal";
import { Panel, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";

/** The external shops a supplier can be given (backend: app/domain/channels.py). */
const SHOPS: { id: string; label: string }[] = [{ id: "etsy", label: "Etsy" }];

type Draft = { id?: number; email: string; full_name: string; password: string; supplier_name: string; channels: string[] };
const blank: Draft = { email: "", full_name: "", password: "", supplier_name: "", channels: ["etsy"] };
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

/**
 * Team → Supplier logins: an account for each supplier that sees only their own orders (the orders whose supplier
 * is this name) on the external shops ticked here — never the rest of the admin.
 */
export function SupplierLogins() {
  const { push } = useToast();
  const [rows, setRows] = useState<User[] | null>(null);
  const [known, setKnown] = useState<string[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    apiFetch<User[]>("/admin/supplier-logins").then(setRows, () => setRows([]));
  }, []);
  useEffect(() => {
    load();
    // Supplier names already on Etsy orders, to pick from (any name can still be typed).
    apiFetch<{ options: { suppliers: string[] } }>("/admin/etsy/supplier-payments/overview").then((r) => setKnown(r.options.suppliers), () => undefined);
  }, [load]);

  const save = async () => {
    if (!draft) return;
    setBusy(true);
    try {
      if (draft.id) {
        await apiFetch(`/admin/supplier-logins/${draft.id}`, { method: "PATCH", body: JSON.stringify({ supplier_name: draft.supplier_name, channels: draft.channels }) });
        push({ title: "Supplier login updated" });
      } else {
        await apiFetch("/admin/supplier-logins", {
          method: "POST",
          body: JSON.stringify({ email: draft.email, password: draft.password, full_name: draft.full_name || null, supplier_name: draft.supplier_name, channels: draft.channels }),
        });
        push({ title: "Supplier login created", description: `Send ${draft.email} their password; they sign in at /login.` });
      }
      setDraft(null);
      load();
    } catch (e) {
      push({ title: "Not saved", description: errorText(e), tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<User>[] = [
    { key: "n", header: "Supplier", cell: (u) => <span className="font-medium">{u.supplier_name ?? "—"}</span> },
    { key: "e", header: "Login", cell: (u) => <span>{u.full_name ? `${u.full_name} · ` : ""}{u.email}</span> },
    { key: "s", header: "Shops", cell: (u) => (u.supplier_channels ?? []).map((c) => SHOPS.find((s) => s.id === c)?.label ?? c).join(", ") || "—" },
    { key: "a", header: "Status", hide: "sm", cell: (u) => <Pill tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Off"}</Pill> },
    {
      key: "x",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (u) => (
        <Button size="sm" variant="secondary" onClick={() => setDraft({ id: u.id, email: u.email, full_name: u.full_name ?? "", password: "", supplier_name: u.supplier_name ?? "", channels: u.supplier_channels ?? [] })}>
          Edit access
        </Button>
      ),
    },
  ];

  const valid = !!draft && draft.supplier_name.trim() && draft.channels.length > 0 && (draft.id || (draft.email.includes("@") && draft.password.length >= 8));
  return (
    <Panel className="mt-6">
      <PanelHeader
        title="Supplier logins"
        description="A login per supplier: they see and ship only their own orders, on the shops you tick, and what they are owed. Switch one off or reset its password in the list above."
        actions={<Button size="sm" onClick={() => setDraft({ ...blank })}>Add supplier login</Button>}
      />
      <DataTable columns={columns} rows={rows} rowKey={(u) => u.id} caption="Supplier logins" empty="No supplier logins yet." />

      <Modal
        open={!!draft}
        onClose={() => setDraft(null)}
        title={draft?.id ? "Supplier access" : "Add supplier login"}
        description="The supplier name must match the Supplier field on orders (it isn't case-sensitive)."
        footer={
          <>
            <Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
            <Button onClick={save} disabled={busy || !valid}>{busy ? "Saving…" : draft?.id ? "Save access" : "Create login"}</Button>
          </>
        }
      >
        {draft ? (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="Supplier name" hint={known.length ? "Pick one used on orders, or type a new one." : undefined}>
                {(p) => (
                  <>
                    <Input {...p} list="supplier-names" value={draft.supplier_name} onChange={(e) => setDraft({ ...draft, supplier_name: e.target.value })} maxLength={200} required />
                    <datalist id="supplier-names">{known.map((k) => <option key={k} value={k} />)}</datalist>
                  </>
                )}
              </Field>
            </div>
            {!draft.id ? (
              <>
                <Field label="Contact name">{(p) => <Input {...p} value={draft.full_name} onChange={(e) => setDraft({ ...draft, full_name: e.target.value })} maxLength={200} />}</Field>
                <Field label="Email (their login)">{(p) => <Input {...p} type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} required />}</Field>
                <div className="sm:col-span-2">
                  <Field label="Password" hint="At least 8 characters. Share it with them privately; they can change it later.">
                    {(p) => <Input {...p} type="password" autoComplete="new-password" value={draft.password} onChange={(e) => setDraft({ ...draft, password: e.target.value })} required />}
                  </Field>
                </div>
              </>
            ) : null}
            <fieldset className="sm:col-span-2">
              <legend className="mb-1.5 text-sm font-medium text-ink">Shops they may see</legend>
              <div className="flex flex-wrap gap-4">
                {SHOPS.map((s) => (
                  <label key={s.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={draft.channels.includes(s.id)}
                      onChange={(e) => setDraft({ ...draft, channels: e.target.checked ? [...draft.channels, s.id] : draft.channels.filter((c) => c !== s.id) })}
                    />
                    {s.label}
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
        ) : null}
      </Modal>
    </Panel>
  );
}
