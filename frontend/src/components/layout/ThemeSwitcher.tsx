"use client";

import { Moon01, Sun as SunIcon } from "@untitledui/icons";
import { useEffect, useState } from "react";
import { useOptionalI18n } from "@/i18n/client";
import { applyTheme, DEFAULT_THEME, resolveTheme, THEME_KEY, THEMES, type ThemeChoice } from "@/lib/themes";
import { cn } from "@/lib/utils";

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(THEME_KEY) as ThemeChoice | null;
    return v === "system" || THEMES.some((t) => t.id === v) ? (v as ThemeChoice) : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

/** Whether Dark is showing now, and a switch that saves the opposite. An older "match my device" choice is kept until the shopper clicks. */
function useDarkMode() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const sync = () => setDark(document.documentElement.dataset.theme === "midnight");
    sync();
    const choice = readChoice();
    window.addEventListener("wcw-theme", sync);
    if (choice !== "system") return () => window.removeEventListener("wcw-theme", sync);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system", true);
    mq.addEventListener("change", onChange);
    return () => {
      window.removeEventListener("wcw-theme", sync);
      mq.removeEventListener("change", onChange);
    };
  }, []);
  const toggle = () => {
    const next: ThemeChoice = resolveTheme(readChoice()) === "midnight" ? "classic" : "midnight";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* private mode: applies for this visit only */
    }
    applyTheme(next, true);
  };
  return [dark, toggle] as const;
}

function Moon({ className }: { className?: string }) {
  return <Moon01 aria-hidden="true" className={className} strokeWidth={1.75} />;
}

function Sun({ className }: { className?: string }) {
  return <SunIcon aria-hidden="true" className={className} strokeWidth={1.75} />;
}

/**
 * Dark mode on/off: one button, no menu. A moon while the page is light (click for Dark), a sun while it is dark.
 * `variant="menu"`: round icon button (header, admin top bar); "inline": icon and words (mobile menu).
 */
export function ThemeSwitcher({ className, variant = "menu" }: { className?: string; variant?: "menu" | "inline" }) {
  const { t } = useOptionalI18n();
  const [dark, toggle] = useDarkMode();
  const tip = dark ? t.theme.toLight : t.theme.toDark;
  const icon = dark ? <Sun className="size-5" /> : <Moon className="size-5" />;

  if (variant === "inline") {
    return (
      <button
        type="button"
        aria-pressed={dark}
        onClick={toggle}
        title={tip}
        className={cn(
          "inline-flex items-center gap-2.5 rounded-[var(--radius-control)] border px-3 py-2 text-sm hover:bg-sand",
          dark ? "border-accent bg-accent-soft font-semibold" : "border-line",
          className,
        )}
      >
        {icon}
        <span>{t.theme.dark}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      aria-label={t.theme.dark}
      aria-pressed={dark}
      onClick={toggle}
      title={tip}
      className={cn("grid size-10 place-items-center rounded-full transition-colors hover:bg-sand", className)}
    >
      {icon}
    </button>
  );
}
