"use client";

import { API_URL } from "./client-api";

/**
 * First-party, consent-based visit tracking. Nothing is collected or sent until the visitor accepts in the banner;
 * declining (or never answering) means no ids are created and no events leave the browser.
 *
 * Kept in this browser: a random visitor id, a visit id that expires after 30 minutes of inactivity, and the
 * choice itself. The server stores no IP address or raw user agent, strips query strings and private tokens from
 * paths, and drops search terms that look like an email address or phone number (backend/app/domain/tracking.py).
 */

export type Consent = "accepted" | "declined";
type EventType =
  | "page_view"
  | "product_view"
  | "search"
  | "add_to_cart"
  | "remove_from_cart"
  | "view_cart"
  | "begin_checkout"
  | "wishlist_add"
  | "newsletter_signup"
  | "coupon_applied"
  | "coupon_failed"
  | "notify_me"
  | "web_vital"
  | "client_error"
  | "recently_viewed_click"
  | "recommendation_click"
  | "share";

interface TrackEvent {
  type: EventType;
  path?: string;
  product_id?: number;
  value?: number;
  data?: Record<string, string | number | boolean | null>;
}

const CONSENT_KEY = "wcw-consent";
const VISITOR_KEY = "wcw-vid";
const SESSION_KEY = "wcw-sid";
const SESSION_IDLE_MS = 30 * 60 * 1000;
const FLUSH_MS = 4000;
const MAX_BATCH = 20;

const listeners = new Set<(c: Consent | null) => void>();
let queue: TrackEvent[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;
let enabled = true; // Admin → Settings → Analytics can switch tracking off for everyone
let locale = "en";

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function randomId(): string {
  const bytes = new Uint8Array(18);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => "abcdefghijklmnopqrstuvwxyz0123456789"[b % 36]).join("");
}

export function getConsent(): Consent | null {
  const v = storage()?.getItem(CONSENT_KEY);
  return v === "accepted" || v === "declined" ? v : null;
}

export function onConsentChange(fn: (c: Consent | null) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Record the visitor's choice (and count it: the server keeps only a daily total, never who chose what). */
export function setConsent(choice: Consent | null) {
  const s = storage();
  if (choice) s?.setItem(CONSENT_KEY, choice);
  else s?.removeItem(CONSENT_KEY);
  if (choice !== "accepted") {
    // Changing your mind removes the ids too.
    s?.removeItem(VISITOR_KEY);
    s?.removeItem(SESSION_KEY);
    queue = [];
  }
  if (choice) {
    fetch(`${API_URL}/events/consent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ accepted: choice === "accepted" }),
    }).catch(() => undefined);
  }
  listeners.forEach((fn) => fn(choice));
}

export function configureAnalytics(opts: { enabled: boolean; locale: string }) {
  enabled = opts.enabled;
  locale = opts.locale;
}

function ids(): { visitor: string; session: string; fresh: boolean } | null {
  const s = storage();
  if (!s || getConsent() !== "accepted" || !enabled) return null;
  let visitor = s.getItem(VISITOR_KEY);
  if (!visitor) {
    visitor = randomId();
    s.setItem(VISITOR_KEY, visitor);
  }
  const now = Date.now();
  let session: { id: string; last: number } | null = null;
  try {
    session = JSON.parse(s.getItem(SESSION_KEY) || "null");
  } catch {
    session = null;
  }
  const fresh = !session || now - session.last > SESSION_IDLE_MS;
  const id = fresh || !session ? randomId() : session.id;
  s.setItem(SESSION_KEY, JSON.stringify({ id, last: now }));
  return { visitor, session: id, fresh };
}

let landing: Record<string, string | undefined> | null = null;

function landingInfo() {
  if (landing) return landing;
  const url = new URL(window.location.href);
  landing = {
    path: url.pathname,
    referrer: document.referrer || undefined,
    utm_source: url.searchParams.get("utm_source") ?? undefined,
    utm_medium: url.searchParams.get("utm_medium") ?? undefined,
    utm_campaign: url.searchParams.get("utm_campaign") ?? undefined,
    locale,
  };
  return landing;
}

/** Send what is queued. `closing`: the page is being hidden, so ask the browser to finish the request anyway. */
export function flush(closing = false) {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  const who = ids();
  if (!who || queue.length === 0) {
    queue = [];
    return;
  }
  const events = queue.splice(0, MAX_BATCH);
  fetch(`${API_URL}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: who.session, visitor_id: who.visitor, landing: landingInfo(), events }),
    keepalive: closing, // keepalive only when needed: some browsers refuse it for cross-site JSON requests
  }).catch(() => undefined);
  if (queue.length) flush(closing);
}

/** Queue one event. Does nothing without consent. */
export function track(type: EventType, event: Omit<TrackEvent, "type"> = {}) {
  if (typeof window === "undefined" || getConsent() !== "accepted" || !enabled) return;
  queue.push({ type, path: event.path ?? window.location.pathname, ...event });
  if (queue.length >= MAX_BATCH) flush();
  else if (!timer) timer = setTimeout(flush, FLUSH_MS);
}

/** Core Web Vitals and page timing, measured in the browser and sent once when the page is hidden. */
export function watchPerformance(): () => void {
  if (typeof PerformanceObserver === "undefined") return () => undefined;
  const vitals: Record<string, number> = {};
  const observers: PerformanceObserver[] = [];
  const observe = (type: string, cb: (entries: PerformanceEntryList) => void) => {
    try {
      const o = new PerformanceObserver((list) => cb(list.getEntries()));
      o.observe({ type, buffered: true } as PerformanceObserverInit);
      observers.push(o);
    } catch {
      /* not supported in this browser */
    }
  };
  observe("largest-contentful-paint", (entries) => {
    const last = entries[entries.length - 1];
    if (last) vitals.LCP = last.startTime;
  });
  observe("paint", (entries) => {
    for (const e of entries) if (e.name === "first-contentful-paint") vitals.FCP = e.startTime;
  });
  let cls = 0;
  observe("layout-shift", (entries) => {
    for (const e of entries as (PerformanceEntry & { value: number; hadRecentInput: boolean })[]) {
      if (!e.hadRecentInput) cls += e.value;
    }
    vitals.CLS = Math.round(cls * 1000) / 1000;
  });
  observe("event", (entries) => {
    for (const e of entries as (PerformanceEntry & { duration: number })[]) vitals.INP = Math.max(vitals.INP ?? 0, e.duration);
  });
  const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  if (nav) vitals.TTFB = nav.responseStart;

  let sent = false;
  const send = () => {
    if (sent || document.visibilityState !== "hidden") return;
    sent = true;
    for (const [name, value] of Object.entries(vitals)) {
      // CLS is a score (0.1 = good); the rest are milliseconds. Values go to the server as numbers with 2 decimals.
      track("web_vital", { value: Math.round(value * 100) / 100, data: { name } });
    }
    flush(true);
  };
  document.addEventListener("visibilitychange", send);
  return () => {
    document.removeEventListener("visibilitychange", send);
    observers.forEach((o) => o.disconnect());
  };
}

/** The current visit id, only when the visitor accepted analytics (lets an order be credited to its traffic channel). */
export function visitSessionId(): string | undefined {
  if (getConsent() !== "accepted" || !enabled) return undefined;
  try {
    const session = JSON.parse(storage()?.getItem(SESSION_KEY) || "null");
    return typeof session?.id === "string" ? session.id : undefined;
  } catch {
    return undefined;
  }
}
