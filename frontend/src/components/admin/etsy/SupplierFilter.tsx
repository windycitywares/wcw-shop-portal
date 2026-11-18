"use client";

import { useCallback, useEffect, useState } from "react";
import { loadSuppliers, type SupplierRow } from "@/components/admin/SupplierSelect";
import { Field, Select } from "@/components/ui/Field";

const KEY = "wcw-etsy-supplier";
export const NO_SUPPLIER = "__none__";

/** The supplier filter shared by every Etsy tab: pick one on the dashboard and Orders, Listings and Payments follow. */
export function useSupplierFilter(): [string, (v: string) => void] {
  const [value, setValue] = useState("");
  useEffect(() => {
    try {
      setValue(sessionStorage.getItem(KEY) ?? "");
    } catch {
      /* storage unavailable */
    }
  }, []);
  const set = useCallback((v: string) => {
    setValue(v);
    try {
      if (v) sessionStorage.setItem(KEY, v);
      else sessionStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }, []);
  return [value, set];
}

/** "All suppliers", "Supplier not set", then the supplier list (switched-off suppliers last, marked). */
export function SupplierFilter({ value, onChange, className = "w-full sm:w-56" }: { value: string; onChange: (v: string) => void; className?: string }) {
  const [rows, setRows] = useState<SupplierRow[]>([]);
  useEffect(() => {
    loadSuppliers().then(setRows, () => setRows([]));
  }, []);
  const known = !value || value === NO_SUPPLIER || rows.some((s) => s.name.toLowerCase() === value.toLowerCase());
  return (
    <Field label="Supplier" className={className}>
      {(p) => (
        <Select {...p} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">All suppliers</option>
          <option value={NO_SUPPLIER}>Supplier not set</option>
          {!known ? <option value={value}>{value}</option> : null}
          {rows.filter((s) => s.is_active).map((s) => <option key={s.id} value={s.name}>{s.name}</option>)}
          {rows.some((s) => !s.is_active) ? (
            <optgroup label="Switched off">
              {rows.filter((s) => !s.is_active).map((s) => <option key={s.id} value={s.name}>{s.name}</option>)}
            </optgroup>
          ) : null}
        </Select>
      )}
    </Field>
  );
}
