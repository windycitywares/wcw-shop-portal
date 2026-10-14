"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/client-api";

/**
 * Cloudflare Turnstile CAPTCHA. The site key comes from the API at runtime (/site-config), so it
 * can be set on the server without rebuilding the storefront. With no key configured nothing is
 * shown and the API skips the check (development).
 *
 * Tokens are single-use: change `resetKey` after a failed submit to get a fresh one.
 */

interface TurnstileApi {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  remove: (id: string) => void;
}
declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let siteKeyPromise: Promise<string | null> | null = null;
let scriptPromise: Promise<void> | null = null;

function getSiteKey() {
  siteKeyPromise ??= apiFetch<{ turnstile_site_key: string | null }>("/site-config")
    .then((c) => c.turnstile_site_key)
    .catch(() => {
      siteKeyPromise = null;
      return null;
    });
  return siteKeyPromise;
}

function loadScript() {
  scriptPromise ??= new Promise<void>((resolve, reject) => {
    if (window.turnstile) return resolve();
    const s = document.createElement("script");
    s.src = SCRIPT;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => {
      scriptPromise = null;
      reject(new Error("Turnstile failed to load"));
    };
    document.head.appendChild(s);
  });
  return scriptPromise;
}

export function Turnstile({
  onToken,
  resetKey = 0,
  locale = "en",
  label,
  action,
}: {
  /** Names the protected form; the API checks the token was solved for this action. */
  action: "signup" | "contact" | "checkout";
  onToken: (token: string | null) => void;
  resetKey?: number;
  locale?: string;
  label: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const tokenCb = useRef(onToken);
  tokenCb.current = onToken;

  useEffect(() => {
    let widget: string | null = null;
    let cancelled = false;
    tokenCb.current(null);
    (async () => {
      const key = await getSiteKey();
      if (cancelled) return;
      setEnabled(!!key);
      if (!key || !box.current) return;
      try {
        await loadScript();
      } catch {
        return;
      }
      if (cancelled || !box.current || !window.turnstile) return;
      widget = window.turnstile.render(box.current, {
        sitekey: key,
        action,
        language: locale,
        theme: document.documentElement.dataset.theme === "midnight" ? "dark" : "light",
        callback: (t: string) => tokenCb.current(t),
        "expired-callback": () => tokenCb.current(null),
        "error-callback": () => tokenCb.current(null),
      });
    })();
    return () => {
      cancelled = true;
      if (widget && window.turnstile) window.turnstile.remove(widget);
    };
  }, [resetKey, locale, action]);

  if (enabled === false) return null;
  return <div ref={box} role="group" aria-label={label} className="min-h-[65px]" />;
}
