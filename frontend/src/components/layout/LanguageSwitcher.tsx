"use client";

import { Globe01 } from "@untitledui/icons";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { useI18n } from "@/i18n/client";
import { LOCALE_COOKIE, localeNames, localePath, locales, stripLocale, type Locale } from "@/i18n/config";
import { cn } from "@/lib/utils";

function remember(locale: Locale) {
  // A manual choice beats the browser language from now on (1 year).
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=31536000; samesite=lax`;
}

/** Same page in another language. Plain links, so it also works without JavaScript. */
export function LanguageSwitcher({ className, variant = "menu" }: { className?: string; variant?: "menu" | "inline" }) {
  const { locale, t } = useI18n();
  const pathname = usePathname() || "/";
  const base = stripLocale(pathname);
  const ref = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    // Close the menu when clicking elsewhere
    const onClick = (e: MouseEvent) => {
      if (ref.current?.open && !ref.current.contains(e.target as Node)) ref.current.open = false;
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  const links = locales.map((l) => (
    <a
      key={l}
      href={localePath(l, base)}
      hrefLang={l}
      lang={l}
      onClick={() => remember(l)}
      aria-current={l === locale ? "true" : undefined}
      className={cn(
        variant === "menu"
          ? "block rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand"
          : "text-sm hover:text-white",
        l === locale && (variant === "menu" ? "font-semibold" : "text-white underline underline-offset-4"),
      )}
    >
      {localeNames[l]}
    </a>
  ));

  if (variant === "inline") {
    return (
      <nav aria-label={t.nav.language} className={className}>
        <ul className="flex gap-4">
          {links.map((link, i) => (
            <li key={locales[i]}>{link}</li>
          ))}
        </ul>
      </nav>
    );
  }

  return (
    <details ref={ref} className={cn("relative", className)}>
      <summary className="flex h-10 cursor-pointer list-none items-center gap-1.5 rounded-full px-3 text-sm hover:bg-sand [&::-webkit-details-marker]:hidden" title={t.nav.language}>
        <Globe01 aria-hidden="true" className="size-4" strokeWidth={1.6} />
        <span className="uppercase" aria-hidden="true">
          {locale}
        </span>
        <span className="sr-only">{`${t.nav.language}: ${localeNames[locale]}`}</span>
      </summary>
      <div className="absolute right-0 top-full z-50 mt-2 w-44 rounded-[var(--radius-control)] border border-line bg-surface p-1.5 shadow-[0_12px_32px_-12px_rgb(23_35_43/0.25)]">
        {links}
      </div>
    </details>
  );
}
