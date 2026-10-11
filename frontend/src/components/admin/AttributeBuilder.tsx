"use client";

import type { AttributeValue } from "@/lib/types";
import { attributeList } from "@/lib/utils";
import { Button } from "@/components/ui/Button";

export interface AttributeRow {
  key: string;
  value: string;
}

export function toRows(attrs: Record<string, AttributeValue>): AttributeRow[] {
  return Object.entries(attrs).map(([key, v]) => ({ key, value: attributeList(v).join(", ") }));
}

/** "Red, Blue" -> ["Red", "Blue"]; "Oak" -> "Oak". Empty keys are dropped. */
export function fromRows(rows: AttributeRow[]): Record<string, AttributeValue> {
  const out: Record<string, AttributeValue> = {};
  for (const { key, value } of rows) {
    const k = key.trim();
    if (!k) continue;
    const parts = value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (parts.length) out[k] = parts.length === 1 ? parts[0] : parts;
  }
  return out;
}

const SUGGESTIONS = ["Material", "Color", "Size", "Dimensions", "Weight", "Finish", "Care", "Engraving"];

/** Dynamic key/value editor for the product's JSONB `attributes`. */
export function AttributeBuilder({ rows, onChange }: { rows: AttributeRow[]; onChange: (rows: AttributeRow[]) => void }) {
  const update = (i: number, patch: Partial<AttributeRow>) =>
    onChange(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  return (
    <fieldset>
      <legend className="text-sm font-medium">Attributes</legend>
      <p className="mt-1 text-xs text-muted">
        Shown as product details and used for shop filters. Separate multiple options with commas (e.g. “Red, Blue”).
      </p>
      <datalist id="attribute-suggestions">
        {SUGGESTIONS.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      <ul className="mt-3 space-y-2">
        {rows.map((row, i) => (
          <li key={i} className="flex gap-2">
            <label className="sr-only" htmlFor={`attr-key-${i}`}>
              Attribute name {i + 1}
            </label>
            <input
              id={`attr-key-${i}`}
              list="attribute-suggestions"
              value={row.key}
              onChange={(e) => update(i, { key: e.target.value })}
              placeholder="Name"
              className="h-10 w-40 rounded-lg border border-line bg-surface px-3 text-sm"
            />
            <label className="sr-only" htmlFor={`attr-value-${i}`}>
              Value for {row.key || `attribute ${i + 1}`}
            </label>
            <input
              id={`attr-value-${i}`}
              value={row.value}
              onChange={(e) => update(i, { value: e.target.value })}
              placeholder="Value(s)"
              className="h-10 flex-1 rounded-lg border border-line bg-surface px-3 text-sm"
            />
            <Button variant="ghost" size="sm" className="h-10" onClick={() => onChange(rows.filter((_, idx) => idx !== i))}>
              Remove<span className="sr-only"> {row.key}</span>
            </Button>
          </li>
        ))}
      </ul>
      <Button variant="secondary" size="sm" className="mt-3" onClick={() => onChange([...rows, { key: "", value: "" }])}>
        Add attribute
      </Button>
    </fieldset>
  );
}
