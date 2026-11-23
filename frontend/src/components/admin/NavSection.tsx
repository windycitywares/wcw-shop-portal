"use client";

import { createContext, useCallback, useContext, useEffect, useId, useState } from "react";
import { cn } from "@/lib/utils";
import { Icon } from "./ui/Icon";

/*
 * The admin sidebar as an accordion (the same pattern as the CRM): each labelled section opens and closes from its
 * heading with a smooth height animation. Going to a page opens the section it is in; everything else stays the way
 * the person left it, remembered in this browser. On the narrow icon rail sections are always open (nothing to fold).
 */

const KEY = "wcw-admin-nav";
type Saved = Record<string, boolean>;

function readSaved(): Saved {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Saved) : {};
  } catch {
    return {};
  }
}

function writeSaved(value: Saved) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    /* private window or blocked storage: the menu still works, it just won't remember */
  }
}

interface NavState {
  isOpen: (key: string) => boolean;
  setOpen: (key: string, open: boolean) => void;
}

const Ctx = createContext<NavState>({ isOpen: () => true, setOpen: () => {} });

/** Holds which sections are open for every `NavSection` inside it. */
export function NavAccordion({ children }: { children: React.ReactNode }) {
  const [saved, setSaved] = useState<Saved>({});
  useEffect(() => setSaved(readSaved()), []);
  const setOpen = useCallback((key: string, open: boolean) => {
    setSaved((s) => {
      if (s[key] === open) return s;
      const next = { ...s, [key]: open };
      writeSaved(next);
      return next;
    });
  }, []);
  const isOpen = useCallback((key: string) => saved[key] !== false, [saved]);
  return <Ctx.Provider value={{ isOpen, setOpen }}>{children}</Ctx.Provider>;
}

/** Smoothly opens to its content's height (CSS grid rows); instant when reduced motion is asked for. */
export function Collapse({ open, id, children }: { open: boolean; id: string; children: React.ReactNode }) {
  return (
    <div
      id={id}
      className={cn(
        "grid transition-[grid-template-rows,opacity] duration-200 ease-out motion-reduce:transition-none",
        open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
      )}
      inert={!open}
    >
      <div className="min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

/** One labelled sidebar section. `holdsCurrent` opens it when the page you are on is inside. */
export function NavSection({ label, holdsCurrent, collapsed, className, children }: {
  label: string | null;
  holdsCurrent: boolean;
  collapsed: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  const id = useId();
  const { isOpen, setOpen } = useContext(Ctx);
  const key = `s:${label ?? ""}`;
  useEffect(() => {
    if (label && holdsCurrent) setOpen(key, true);
  }, [label, holdsCurrent, key, setOpen]);

  if (!label) return <div className={className}>{children}</div>;
  if (collapsed) {
    return (
      <div className={className}>
        <hr className="mx-2 mb-2 border-line" />
        {children}
      </div>
    );
  }
  const open = isOpen(key);
  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => setOpen(key, !open)}
        aria-expanded={open}
        aria-controls={id}
        className="font-admin flex w-full items-center justify-between rounded-[var(--radius-control)] px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted hover:text-ink"
      >
        <span>{label}</span>
        {!open && holdsCurrent && <span className="sr-only">(holds this page)</span>}
        <Icon name="chevronDown" className={cn("ml-auto size-3.5 transition-transform duration-200 motion-reduce:transition-none", open ? "rotate-0" : "-rotate-90")} />
      </button>
      <Collapse open={open} id={id}>{children}</Collapse>
    </div>
  );
}
