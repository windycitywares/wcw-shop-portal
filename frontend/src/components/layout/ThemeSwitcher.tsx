"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useI18n } from "@/i18n/client";
import { applyTheme, DEFAULT_THEME, THEME_KEY, THEMES, type ThemeChoice } from "@/lib/themes";
import { cn } from "@/lib/utils";

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(THEME_KEY) as ThemeChoice | null;
    return v === "system" || THEMES.some((t) => t.id === v) ? (v as ThemeChoice) : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

function useThemeChoice() {
  const [choice, setChoice] = useState<ThemeChoice>(DEFAULT_THEME);
  useEffect(() => setChoice(readChoice()), []);
  useEffect(() => {
    if (choice !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system", true);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [choice]);
  const choose = (c: ThemeChoice) => {
    setChoice(c);
    try {
      localStorage.setItem(THEME_KEY, c);
    } catch {
      /* private mode: applies for this visit only */
    }
    applyTheme(c, true);
  };
  return [choice, choose] as const;
}

function Swatch({ colors, className }: { colors: readonly string[]; className?: string }) {
  return (
    <span aria-hidden="true" className={cn("relative inline-flex size-7 shrink-0 overflow-hidden rounded-full border border-line", className)}>
      <span className="h-full w-1/2" style={{ background: colors[0] }} />
      <span className="h-full w-1/2" style={{ background: colors[1] }} />
      <span className="absolute inset-[30%] rounded-full" style={{ background: colors[2] }} />
    </span>
  );
}

const SYSTEM_SWATCH = ["#f2f3ef", "#0f151c", "#c9902f"] as const;

/** Radio group of themes. `variant="menu"`: palette button + popover (header); "inline": row of swatches (mobile menu). */
export function ThemeSwitcher({ className, variant = "menu" }: { className?: string; variant?: "menu" | "inline" }) {
  const { t } = useI18n();
  const [choice, choose] = useThemeChoice();
  const name = useId();
  const ref = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    if (variant !== "menu") return;
    const onClick = (e: MouseEvent) => {
      if (ref.current?.open && !ref.current.contains(e.target as Node)) ref.current.open = false;
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && ref.current?.open) {
        ref.current.open = false;
        ref.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [variant]);

  const options = [
    ...THEMES.map((th) => ({ id: th.id as ThemeChoice, label: t.theme[th.id], swatch: th.swatch })),
    { id: "system" as ThemeChoice, label: t.theme.system, swatch: SYSTEM_SWATCH },
  ];

  const group = (
    <fieldset className={variant === "inline" ? "flex flex-wrap gap-2" : "space-y-0.5"}>
      <legend className={variant === "menu" ? "px-3 pb-1.5 pt-1 text-xs font-semibold uppercase tracking-wider text-muted" : "sr-only"}>
        {t.theme.choose}
      </legend>
      {options.map((o) => (
        <label
          key={o.id}
          className={cn(
            "flex cursor-pointer items-center gap-3 rounded-[var(--radius-control)] text-sm has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent",
            variant === "menu" ? "px-3 py-2 hover:bg-sand" : "border border-line px-2.5 py-1.5",
            choice === o.id && (variant === "menu" ? "bg-accent-soft font-semibold" : "border-accent bg-accent-soft font-semibold"),
          )}
        >
          <input
            type="radio"
            name={name}
            value={o.id}
            checked={choice === o.id}
            onChange={() => choose(o.id)}
            className="sr-only"
          />
          <Swatch colors={o.swatch} className={variant === "inline" ? "size-5" : undefined} />
          <span className="flex-1">{o.label}</span>
          {variant === "menu" && choice === o.id && (
            <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 text-accent" fill="currentColor">
              <path d="M7.7 13.3 4.4 10l-1.2 1.2 4.5 4.5 9.1-9.1-1.2-1.2z" />
            </svg>
          )}
        </label>
      ))}
    </fieldset>
  );

  if (variant === "inline") return <div className={className}>{group}</div>;

  return (
    <details ref={ref} className={cn("relative", className)}>
      <summary
        className="grid size-10 cursor-pointer list-none place-items-center rounded-full hover:bg-sand [&::-webkit-details-marker]:hidden"
        title={t.theme.label}
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.6">
          <path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.7-.8 1.7-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-.9.8-1.7 1.7-1.7H16a5 5 0 0 0 5-5c0-4-4-7.2-9-7.2Z" />
          <circle cx="7.5" cy="11.5" r="1.2" fill="currentColor" />
          <circle cx="10.5" cy="7.5" r="1.2" fill="currentColor" />
          <circle cx="15" cy="7.8" r="1.2" fill="currentColor" />
        </svg>
        <span className="sr-only">{t.theme.label}</span>
      </summary>
      <div className="absolute right-0 top-full z-50 mt-2 w-56 rounded-[var(--radius-control)] border border-line bg-surface p-1.5 shadow-[0_12px_32px_-12px_rgb(0_0_0/0.3)]">
        {group}
      </div>
    </details>
  );
}
