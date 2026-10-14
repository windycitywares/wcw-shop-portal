"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { HELP_NAV } from "@/content/help";
import { useI18n } from "@/i18n/client";
import { configureAnalytics, flush, getConsent, onConsentChange, setConsent, track, watchPerformance, type Consent } from "@/lib/analytics";
import { apiFetch } from "@/lib/client-api";
import type { ShopConfig } from "@/lib/types";
import { Button } from "@/components/ui/Button";

/** Consent banner + page views, web vitals and script errors (only after the visitor accepts). */
export function Analytics() {
  const { t, locale, href } = useI18n();
  const pathname = usePathname();
  const [consent, setConsentState] = useState<Consent | null | undefined>(undefined); // undefined = not read yet
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    setConsentState(getConsent());
    const off = onConsentChange(setConsentState);
    apiFetch<ShopConfig>(`/shop/config?lang=${locale}`)
      .then((c) => {
        setEnabled(c.analytics_enabled);
        configureAnalytics({ enabled: c.analytics_enabled, locale });
      })
      .catch(() => undefined);
    return off;
  }, [locale]);

  // A page view per route change.
  useEffect(() => {
    if (enabled && consent === "accepted") track("page_view", { path: window.location.pathname });
  }, [pathname, enabled, consent]);

  useEffect(() => {
    if (!enabled || consent !== "accepted") return;
    const stopPerf = watchPerformance();
    const onError = (e: ErrorEvent) => track("client_error", { data: { message: String(e.message).slice(0, 120) } });
    const onHide = () => {
      if (document.visibilityState === "hidden") flush(true);
    };
    window.addEventListener("error", onError);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      stopPerf();
      window.removeEventListener("error", onError);
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [enabled, consent]);

  if (!enabled || consent !== null) return null;
  return (
    <section
      aria-label={t.consent.label}
      className="fixed inset-x-3 bottom-3 z-40 mx-auto max-w-xl rounded-[var(--radius-card)] border border-line bg-surface p-5 shadow-xl sm:inset-x-6"
    >
      <p className="font-serif text-lg">{t.consent.title}</p>
      <p className="mt-1 text-sm text-muted">
        {t.consent.text}{" "}
        <Link href={href("/help/privacy")} className="underline">
          {HELP_NAV[locale].privacy}
        </Link>
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" onClick={() => setConsent("accepted")}>
          {t.consent.accept}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setConsent("declined")}>
          {t.consent.decline}
        </Button>
      </div>
    </section>
  );
}

/** Footer link that brings the banner back so the visitor can change their choice. */
export function ConsentSettingsLink({ className }: { className?: string }) {
  const { t } = useI18n();
  return (
    <button type="button" className={className} onClick={() => setConsent(null)}>
      {t.consent.settings}
    </button>
  );
}
