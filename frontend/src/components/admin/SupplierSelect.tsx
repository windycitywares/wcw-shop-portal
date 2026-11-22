"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/client-api";
import { Select } from "@/components/ui/Field";

export interface SupplierRow {
  id: number;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  notes: string | null;
  is_active: boolean;
  crm_id?: number | null;
  listings: number;
  open_orders: number;
  owed: string;
  logins: number;
}

let cache: Promise<SupplierRow[]> | null = null;
/** The supplier list, fetched once per page view and shared by every picker on the page. */
export function loadSuppliers(fresh = false): Promise<SupplierRow[]> {
  if (!cache || fresh) cache = apiFetch<SupplierRow[]>("/admin/suppliers").catch((e) => { cache = null; throw e; });
  return cache;
}

/**
 * Pick a supplier from the list (External shops → Suppliers). The current value stays selectable even if that supplier
 * was switched off since; new choices are active suppliers only.
 */
export function SupplierSelect({ value, onChange, id, ...rest }: {
  value: string;
  onChange: (v: string) => void;
  id?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
}) {
  const [rows, setRows] = useState<SupplierRow[] | null>(null);
  useEffect(() => {
    loadSuppliers().then(setRows, () => setRows([]));
  }, []);
  const active = (rows ?? []).filter((s) => s.is_active);
  const known = active.some((s) => s.name.toLowerCase() === value.toLowerCase());
  return (
    <div className="grid gap-1">
      <Select id={id} {...rest} value={value} onChange={(e) => onChange(e.target.value)} disabled={!rows}>
        <option value="">{rows ? "No supplier" : "Loading suppliers…"}</option>
        {value && !known ? <option value={value}>{value} (not in the active list)</option> : null}
        {active.map((s) => <option key={s.id} value={s.name}>{s.name}</option>)}
      </Select>
      {rows && active.length === 0 ? (
        <span className="text-xs text-muted">No suppliers yet. <Link href="/admin/suppliers" className="underline">Add one</Link>.</span>
      ) : null}
    </div>
  );
}
