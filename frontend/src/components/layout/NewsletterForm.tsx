"use client";

import { useState } from "react";
import { useI18n } from "@/i18n/client";
import { apiFetch } from "@/lib/client-api";
import { useShopConfig } from "@/lib/shop";
import { formatPrice } from "@/lib/utils";

export function NewsletterForm() {
  const { t, fmt, locale } = useI18n();
  const config = useShopConfig();
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email") || "");
    setState("sending");
    try {
      const res = await apiFetch<{ detail: string; welcome_sent: boolean }>("/newsletter", {
        method: "POST",
        body: JSON.stringify({ email, locale }),
      });
      setMessage(res.welcome_sent ? fmt(t.footer.welcomeSent, { email }) : t.footer.thanks);
      setState("done");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : t.auth.error);
      setState("error");
    }
  }

  const offer = config?.welcome_offer;
  const offerText = offer
    ? fmt(t.footer.newsletterOffer, {
        offer:
          offer.kind === "percent"
            ? fmt(t.footer.offerPercent, { value: offer.value })
            : fmt(t.footer.offerFixed, { amount: formatPrice(offer.value, config?.currency ?? "USD", locale) }),
      })
    : null;

  return (
    <div className="mt-6">
      {offerText && <p className="mb-3 text-sm text-white">{offerText}</p>}
      <form onSubmit={onSubmit} className="flex gap-2">
        <label htmlFor="newsletter-email" className="sr-only">
          {t.footer.email}
        </label>
        <input
          id="newsletter-email"
          name="email"
          type="email"
          required
          autoComplete="email"
          placeholder={t.footer.emailPlaceholder}
          className="h-11 min-w-0 flex-1 rounded-[var(--radius-control)] border border-white/20 bg-white/5 px-4 text-sm text-white placeholder:text-night-muted focus-visible:border-white/60"
        />
        <button
          type="submit"
          disabled={state === "sending"}
          className="h-11 rounded-[var(--radius-control)] bg-white px-5 text-sm font-medium text-night hover:bg-sand disabled:opacity-60"
        >
          {state === "sending" ? t.footer.subscribing : t.footer.subscribe}
        </button>
      </form>
      <p role="status" aria-live="polite" className={state === "error" ? "mt-2 text-sm text-[#f0a597]" : "mt-2 text-sm text-white"}>
        {state === "done" || state === "error" ? message : ""}
      </p>
    </div>
  );
}
