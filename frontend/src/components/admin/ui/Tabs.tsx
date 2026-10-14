"use client";

import { useId, useRef } from "react";
import { cn } from "@/lib/utils";

export interface TabItem<T extends string> {
  id: T;
  label: string;
  /** Small count after the label ("Pending 3"). */
  count?: number;
}

/** Filter-style tabs (All / Pending / Approved…). The caller renders the matching content. */
export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
  className,
}: {
  tabs: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  label: string;
  className?: string;
}) {
  const base = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function onKey(e: React.KeyboardEvent, i: number) {
    const next = e.key === "ArrowRight" ? (i + 1) % tabs.length : e.key === "ArrowLeft" ? (i - 1 + tabs.length) % tabs.length : null;
    if (next == null) return;
    e.preventDefault();
    onChange(tabs[next].id);
    refs.current[next]?.focus();
  }
  return (
    <div role="tablist" aria-label={label} className={cn("flex gap-1 overflow-x-auto border-b border-line", className)}>
      {tabs.map((t, i) => {
        const selected = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            id={`${base}-${t.id}`}
            role="tab"
            type="button"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.id)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              "-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              selected ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {t.label}
            {t.count != null && <span className={cn("num rounded-full px-1.5 text-xs", selected ? "bg-accent-soft text-accent-strong" : "bg-sand text-muted")}>{t.count}</span>}
          </button>
        );
      })}
    </div>
  );
}
