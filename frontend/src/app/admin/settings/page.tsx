"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { SETTINGS_TABS, TOOL_ABOUT, settingsPages } from "@/components/admin/nav";
import { Icon } from "@/components/admin/ui/Icon";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

type Value = string | number | boolean | null | string[] | Record<string, string>;
type Settings = Record<string, Record<string, Value>>;

type Def =
  | { key: string; label: string; hint?: string; type: "bool" }
  | { key: string; label: string; hint?: string; type: "number" | "money"; min?: number; max?: number; optional?: boolean }
  | { key: string; label: string; hint?: string; type: "text" | "email" }
  | { key: string; label: string; hint?: string; type: "select"; options: readonly (readonly [string, string])[] }
  | { key: string; label: string; hint?: string; type: "secret" }
  | { key: string; label: string; hint?: string; type: "list"; upper?: boolean }
  | { key: string; label: string; hint?: string; type: "langs"; long?: boolean };

interface Group {
  id: string;
  label: string;
  description: string;
  fields: Def[];
}

/** Every setting the shop owner can change, in plain words (backend/app/schemas/settings.py has the rules). */
const GROUPS: Group[] = [
  {
    id: "shipping",
    label: "Shipping",
    description: "What shipping costs and how long it takes. The cart, checkout and the Shipping help page all use these.",
    fields: [
      { key: "flat_rate", label: "Shipping per order ($)", type: "money", min: 0 },
      { key: "free_threshold", label: "Free shipping from ($)", hint: "Empty: no free shipping.", type: "money", min: 0, optional: true },
      { key: "allowed_countries", label: "Countries you ship to", hint: "Two-letter codes, comma separated, e.g. US, CA.", type: "list", upper: true },
      { key: "international_rate", label: "Shipping outside the US ($, optional)", type: "money", min: 0, optional: true },
      { key: "handling_days_min", label: "Days to prepare: from", type: "number", min: 0, max: 60 },
      { key: "handling_days_max", label: "Days to prepare: to", type: "number", min: 0, max: 60 },
      { key: "transit_days_min", label: "Days in transit: from", type: "number", min: 0, max: 60 },
      { key: "transit_days_max", label: "Days in transit: to", type: "number", min: 0, max: 60 },
    ],
  },
  {
    id: "tax",
    label: "Sales tax",
    description: "Off until you set your rate. Ask your accountant which rate applies (Illinois includes local rates).",
    fields: [
      { key: "enabled", label: "Collect sales tax", type: "bool" },
      { key: "rate_percent", label: "Rate (%)", type: "number", min: 0, max: 30 },
      { key: "regions", label: "States where you collect it", hint: "e.g. IL", type: "list", upper: true },
      { key: "shipping_taxable", label: "Shipping is taxable too", type: "bool" },
      { key: "label", label: "Name on receipts", type: "text" },
    ],
  },
  {
    id: "payments",
    label: "Payments",
    description:
      "Card payments switch on by themselves once the Stripe keys are on the server. “Pay later” is no longer offered at checkout; orders placed before that change still show these instructions.",
    fields: [
      { key: "manual_instructions", label: "Instructions for an order that is waiting for money", hint: "Bank details, Zelle, check address… Shown on older “pay later” orders and in their email.", type: "langs", long: true },
    ],
  },
  {
    id: "welcome",
    label: "Welcome offer",
    description: "A personal code emailed to new newsletter subscribers who haven't ordered yet.",
    fields: [
      { key: "enabled", label: "Send a welcome code", type: "bool" },
      { key: "percent", label: "Percent off", type: "number", min: 1, max: 60 },
      { key: "expires_days", label: "Valid for (days)", type: "number", min: 1, max: 365 },
      { key: "min_subtotal", label: "Minimum order ($)", type: "money", min: 0 },
    ],
  },
  {
    id: "cart_recovery",
    label: "Cart reminders",
    description:
      "Gentle reminders after a cart is left. Signed-in customers are reminded by default; guests only when they tick the box at checkout, unless you email everyone who leaves an address. Nobody who unsubscribed, or who has ordered since, is reminded.",
    fields: [
      { key: "enabled", label: "Send cart reminders", type: "bool" },
      { key: "remind_signed_in", label: "Remind signed-in customers without asking (recommended; every reminder has an unsubscribe link)", type: "bool" },
      { key: "email_everyone", label: "Email every shopper who leaves an email (not only those who tick the box)", type: "bool" },
      { key: "first_delay_hours", label: "First reminder after (hours)", type: "number", min: 1, max: 720 },
      { key: "second_delay_hours", label: "Second reminder after (hours)", type: "number", min: 2, max: 1440 },
      { key: "max_reminders", label: "Reminders at most", type: "number", min: 0, max: 3 },
      { key: "second_offer_percent", label: "Code in the second reminder (% off, 0 = none)", type: "number", min: 0, max: 40 },
    ],
  },
  {
    id: "reviews",
    label: "Reviews",
    description: "How reviews are collected and published.",
    fields: [
      { key: "auto_approve_verified", label: "Publish reviews from verified buyers straight away (reviews with links still wait)", type: "bool" },
      { key: "request_enabled", label: "Ask for a review after delivery", type: "bool" },
      { key: "request_after_days", label: "Ask after (days)", type: "number", min: 1, max: 90 },
    ],
  },
  {
    id: "analytics",
    label: "Analytics",
    description: "Visit statistics, only for visitors who accept them in the banner. No IP addresses are stored.",
    fields: [
      { key: "enabled", label: "Collect visit statistics", type: "bool" },
      { key: "retention_days", label: "Keep statistics for (days)", type: "number", min: 30, max: 1100 },
    ],
  },
  {
    id: "digest",
    label: "Weekly email",
    description: "A Monday-morning summary of last week's numbers and the top suggestions.",
    fields: [
      { key: "enabled", label: "Send the weekly email", type: "bool" },
      { key: "recipients", label: "Send to", hint: "Email addresses, comma separated. Empty: the order alert address.", type: "list" },
    ],
  },
  {
    id: "general",
    label: "General",
    description: "Banner, order alerts and checkout rules.",
    fields: [
      { key: "announcement_enabled", label: "Show the announcement bar", type: "bool" },
      { key: "announcement", label: "Announcement", hint: "One short line at the top of every page.", type: "langs" },
      { key: "order_alert_email", label: "Email new orders to", type: "email" },
      { key: "low_stock_threshold", label: "“Almost gone” from (units)", type: "number", min: 0, max: 1000 },
      { key: "max_quantity_per_line", label: "Most of one item per order", type: "number", min: 1, max: 100 },
      { key: "guest_checkout", label: "Allow checkout without an account", type: "bool" },
    ],
  },
];

const LANGS = [
  ["en", "English"],
  ["es", "Spanish"],
  ["nl", "Dutch"],
] as const;

function GroupForm({ group, initial, onSaved, status }: { group: Group; initial: Record<string, Value>; onSaved: (s: Settings, status?: Record<string, boolean>) => void; status?: Record<string, boolean> }) {
  const { push } = useToast();
  const [values, setValues] = useState<Record<string, Value>>(initial);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => setValues(initial), [initial]);

  const set = (key: string, v: Value) => setValues((old) => ({ ...old, [key]: v }));
  const changed = group.fields.filter((f) => JSON.stringify(values[f.key]) !== JSON.stringify(initial[f.key]));

  async function save() {
    setBusy(true);
    setProblem("");
    try {
      const patch = Object.fromEntries(
        changed.map((f) => [f.key, f.type === "list" ? ((values[f.key] as string[]) ?? []).filter(Boolean) : values[f.key]]),
      );
      const res = await apiFetch<{ settings: Settings; status?: Record<string, boolean> }>(`/admin/settings/${group.id}`, { method: "PUT", body: JSON.stringify(patch) });
      onSaved(res.settings, res.status);
      push({ title: "Settings saved", description: group.label });
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Couldn't save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel>
      <PanelHeader title={group.label} description={group.description} />
      <PanelBody className="space-y-4">
        {problem && <Alert tone="danger">{problem}</Alert>}
        {group.fields.map((f) => {
          const v = values[f.key];
          if (f.type === "bool") {
            return (
              <label key={f.key} className="flex items-start gap-3 text-sm">
                <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={!!v} onChange={(e) => set(f.key, e.target.checked)} />
                <span>{f.label}</span>
              </label>
            );
          }
          if (f.type === "select") {
            return (
              <Field key={f.key} label={f.label} hint={f.hint}>
                {(p) => (
                  <select
                    {...p}
                    value={(v as string) ?? ""}
                    onChange={(e) => set(f.key, e.target.value || null)}
                    className="h-10 w-full max-w-md rounded-[var(--radius-control)] border border-line bg-white px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
                  >
                    {f.options.map(([val, name]) => (
                      <option key={val} value={val}>
                        {name}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            );
          }
          if (f.type === "secret") {
            const saved = group.id === "email" && status?.email_password_set;
            return (
              <Field key={f.key} label={f.label} hint={f.hint}>
                {(p) => (
                  <Input
                    {...p}
                    type="password"
                    autoComplete="new-password"
                    placeholder={saved ? "•••••••• (saved)" : ""}
                    value={(v as string) ?? ""}
                    onChange={(e) => set(f.key, e.target.value)}
                    className="max-w-md"
                  />
                )}
              </Field>
            );
          }
          if (f.type === "langs") {
            const map = (v as Record<string, string>) ?? {};
            return (
              <fieldset key={f.key} className="space-y-2">
                <legend className="text-sm font-medium">{f.label}</legend>
                {f.hint && <p className="text-xs text-muted">{f.hint}</p>}
                {LANGS.map(([code, name]) => (
                  <Field key={code} label={name}>
                    {(p) =>
                      f.long ? (
                        <Textarea {...p} value={map[code] ?? ""} onChange={(e) => set(f.key, { ...map, [code]: e.target.value })} maxLength={1000} className="min-h-20" />
                      ) : (
                        <Input {...p} value={map[code] ?? ""} onChange={(e) => set(f.key, { ...map, [code]: e.target.value })} maxLength={200} />
                      )
                    }
                  </Field>
                ))}
              </fieldset>
            );
          }
          if (f.type === "list") {
            return (
              <Field key={f.key} label={f.label} hint={f.hint}>
                {(p) => (
                  <Input
                    {...p}
                    value={((v as string[]) ?? []).join(", ")}
                    onChange={(e) =>
                      set(
                        f.key,
                        e.target.value
                          .split(",")
                          .map((x) => (f.upper ? x.trim().toUpperCase() : x.trim()))
                          .filter((x, i, all) => x || i === all.length - 1),
                      )
                    }
                  />
                )}
              </Field>
            );
          }
          if (f.type === "number" || f.type === "money") {
            return (
              <Field key={f.key} label={f.label} hint={f.hint}>
                {(p) => (
                  <Input
                    {...p}
                    type="number"
                    inputMode="decimal"
                    min={f.min}
                    max={f.max}
                    step={f.type === "money" ? 0.01 : 1}
                    value={v == null ? "" : String(v)}
                    onChange={(e) => set(f.key, e.target.value === "" ? (f.optional ? null : 0) : Number(e.target.value))}
                    className="max-w-48"
                  />
                )}
              </Field>
            );
          }
          return (
            <Field key={f.key} label={f.label} hint={f.hint}>
              {(p) => <Input {...p} type={f.type === "email" ? "email" : "text"} value={(v as string) ?? ""} onChange={(e) => set(f.key, e.target.value || null)} className="max-w-md" />}
            </Field>
          );
        })}
        <div className="flex items-center gap-3 pt-2">
          <Button disabled={busy || changed.length === 0} onClick={save}>
            Save changes
          </Button>
          {changed.length > 0 && (
            <Button variant="ghost" onClick={() => setValues(initial)}>
              Undo changes
            </Button>
          )}
        </div>
      </PanelBody>
    </Panel>
  );
}

const STATUS_LABEL: Record<string, string> = {
  stripe_configured: "Card payments (Stripe keys)",
  stripe_webhook_configured: "Stripe payment confirmations (webhook)",
  email_configured: "Sending email (SMTP)",
  captcha_configured: "Spam protection (Turnstile)",
  production: "Live mode",
};

function SettingsInner() {
  const searchParams = useSearchParams();
  const wanted = searchParams.get("tab");
  const tab = GROUPS.some((g) => g.id === wanted) ? (wanted as string) : null;
  const { can } = useAuth();
  const [data, setData] = useState<{ settings: Settings; status: Record<string, boolean> } | null>(null);
  const [error, setError] = useState("");


  useEffect(() => {
    apiFetch<{ settings: Settings; status: Record<string, boolean> }>("/admin/settings").then(setData, (e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (searchParams.get("tab") === "email") window.location.replace("/admin/email");
  }, [searchParams]);

  const group = GROUPS.find((g) => g.id === tab);
  const tools = settingsPages().filter((i) => !i.permission || can(i.permission));
  return (
    <div>
      <PageHeader
        title="Settings"
        description={group ? group.description : "Everything the shop runs by. Pick a topic below, or use the menu on the left to move around."}
        actions={
          group ? (
            <Link href="/admin/settings" className="inline-flex items-center gap-1 text-sm font-medium text-accent underline">
              <Icon name="chevronLeft" className="size-4" />
              All settings
            </Link>
          ) : undefined
        }
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      {data && !group && (
        <Panel className="mb-6">
          <PanelHeader title="Setup status" description="Payments and spam protection are set on the server (backend .env); email is set under Email sending. Green means it's in place." />
          <PanelBody>
            <ul className="flex flex-wrap gap-2">
              {Object.entries(STATUS_LABEL).map(([key, label]) => (
                <li key={key}>
                  <Pill tone={data.status[key] ? "success" : "warning"}>
                    {label}: {data.status[key] ? "ready" : "not set"}
                  </Pill>
                </li>
              ))}
            </ul>
            <Link href="/admin/email" className="mt-4 inline-block text-sm font-medium text-accent underline">
              Email sending settings and test
            </Link>
          </PanelBody>
        </Panel>
      )}
      {group ? (
        <div className="max-w-4xl">
          {data ? (
            <GroupForm key={group.id} group={group} initial={data.settings[group.id] ?? {}} status={data.status} onSaved={(settings, status) => setData({ settings, status: status ?? data.status })} />
          ) : (
            <div className="skeleton h-64" />
          )}
        </div>
      ) : (
        <div className="space-y-8">
          <section aria-labelledby="store-settings">
            <h2 id="store-settings" className="mb-3 text-base font-semibold">
              Your shop
            </h2>
            <ul className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {SETTINGS_TABS.map((t) => (
                <li key={t.id}>
                  <Link href={`/admin/settings?tab=${t.id}`} className="block h-full rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                    <span className="font-medium">{t.label}</span>
                    <span className="mt-1 block text-sm text-muted">{t.about}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
          <section aria-labelledby="admin-tools">
            <h2 id="admin-tools" className="mb-3 text-base font-semibold">
              Email, team and tools
            </h2>
            <ul className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {tools.map((i) => (
                <li key={i.href}>
                  <Link href={i.href} className="flex h-full gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                    <Icon name={i.icon} className="mt-0.5 size-5 shrink-0 text-muted" />
                    <span>
                      <span className="font-medium">{i.label}</span>
                      <span className="mt-1 block text-sm text-muted">{TOOL_ABOUT[i.href] ?? ""}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}

export default function AdminSettings() {
  return (
    <Suspense fallback={<div className="skeleton h-64" />}>
      <SettingsInner />
    </Suspense>
  );
}
