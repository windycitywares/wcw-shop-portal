"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { getConsent, onConsentChange, type Consent } from "@/lib/analytics";
import { apiFetch } from "@/lib/client-api";
import type { ShopConfig } from "@/lib/types";

declare global {
  interface Window {
    __wcwScripts?: boolean;
  }
}

/** Turn pasted HTML into live nodes: <script> tags must be re-created or the browser will not run them. */
function mount(html: string, parent: HTMLElement) {
  const tpl = document.createElement("template");
  tpl.innerHTML = html;
  tpl.content.childNodes.forEach((node) => {
    if (node instanceof HTMLScriptElement) {
      const script = document.createElement("script");
      for (const a of Array.from(node.attributes)) script.setAttribute(a.name, a.value);
      script.text = node.text;
      script.dataset.wcwInjected = "1";
      parent.appendChild(script);
    } else {
      const copy = node.cloneNode(true);
      if (copy instanceof HTMLElement) copy.dataset.wcwInjected = "1";
      parent.appendChild(copy);
    }
  });
}

/** Adds the snippets from Admin → Settings → Tracking code to the storefront (once per page load). */
export function SiteScripts() {
  const pathname = usePathname();
  const [config, setConfig] = useState<ShopConfig | null>(null);
  const [consent, setConsent] = useState<Consent | null>(null);

  useEffect(() => {
    setConsent(getConsent());
    const off = onConsentChange(setConsent);
    apiFetch<ShopConfig>("/shop/config")
      .then(setConfig)
      .catch(() => undefined);
    return off;
  }, []);

  useEffect(() => {
    if (!config || window.__wcwScripts || pathname.startsWith("/admin")) return;
    const head = (config.head_code ?? "").trim();
    const body = (config.body_code ?? "").trim();
    if (!head && !body) return;
    if ((config.scripts_need_consent ?? true) && consent !== "accepted") return;
    window.__wcwScripts = true;
    try {
      if (head) mount(head, document.head);
      if (body) mount(body, document.body);
    } catch {
      /* a broken snippet must never break the shop */
    }
  }, [config, consent, pathname]);

  return null;
}
