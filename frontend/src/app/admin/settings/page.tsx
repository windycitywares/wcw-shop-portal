"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Icon } from "@/components/admin/ui/Icon";
import { NAV } from "@/components/admin/nav";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

type Value = string | number | boolean | null | string[] | Record<string, string>;
type Settings = Record<string, Record<string, Value>>;

type Def =
  | { key: string; label: string; hint?: string; type: "bool" }
  | { key: string; label: string; hint?: string; type: "number" | "money"; min?: number; max?: number; optional?: boolean }
  | { key: string; label: string; hint?: string; type: "text" | "email" }
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
      "Gentle reminders after a cart is left. By default only shoppers who tick the box at checkout are emailed; the last option emails everyone who leaves an address there.",
    fields: [
      { key: "enabled", label: "Send cart reminders", type: "bool" },
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

function GroupForm({ group, initial, onSaved }: { group: Group; initial: Record<string, Value>; onSaved: (s: Settings) => void }) {
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
      const res = await apiFetch<{ settings: Settings }>(`/admin/settings/${group.id}`, { method: "PUT", body: JSON.stringify(patch) });
      onSaved(res.settings);
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

export default function AdminSettings() {
  const { push } = useToast();
  const { user, can } = useAuth();
  const [tab, setTab] = useState("shipping");
  const [data, setData] = useState<{ settings: Settings; status: Record<string, boolean> } | null>(null);
  const [error, setError] = useState("");

  const adminSections = (NAV.find((g) => g.label === "Settings")?.items ?? []).filter(
    (i) => i.href !== "/admin/settings" && (!i.permission || can(i.permission)),
  );

  useEffect(() => {
    apiFetch<{ settings: Settings; status: Record<string, boolean> }>("/admin/settings").then(setData, (e) => setError(e.message));
    const t = new URLSearchParams(window.location.search).get("tab");
    if (t && GROUPS.some((g) => g.id === t)) setTab(t);
  }, []);

  const group = GROUPS.find((g) => g.id === tab) ?? GROUPS[0];
  return (
    <div>
      <PageHeader title="Settings" description="Everything the shop runs by: shipping, tax, payments, emails and rules, plus the audit log, test mode, backups and deployments." />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      {data && (
        <Panel className="mb-6">
          <PanelHeader title="Server setup" description="These are set on the server (backend .env), not here. Green means it's in place." />
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
            <Button
              size="sm"
              variant="secondary"
              className="mt-4"
              onClick={() =>
                apiFetch<{ detail: string }>("/admin/settings/test-email", { method: "POST" }).then(
                  (r) => push({ title: "Test email sent", description: r.detail }),
                  (e) => push({ title: "Email not sent", description: e.message, tone: "danger" }),
                )
              }
            >
              Send a test email to {user?.email ?? "me"}
            </Button>
          </PanelBody>
        </Panel>
      )}
      <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label="Settings sections" className="space-y-1">
          {GROUPS.map((g) => (
            <button
              key={g.id}
              type="button"
              onClick={() => {
                setTab(g.id);
                window.history.replaceState(null, "", `?tab=${g.id}`);
              }}
              className={`block w-full rounded-[var(--radius-control)] px-3 py-2 text-left text-sm ${tab === g.id ? "bg-sand font-medium text-ink" : "text-muted hover:bg-sand/60 hover:text-ink"}`}
            >
              {g.label}
            </button>
          ))}
          {adminSections.length > 0 && (
            <>
              <p className="px-3 pb-1 pt-4 text-xs font-medium uppercase tracking-wide text-muted">Admin</p>
              {adminSections.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-2 rounded-[var(--radius-control)] px-3 py-2 text-sm text-muted hover:bg-sand/60 hover:text-ink"
                >
                  <Icon name={item.icon} className="size-4" />
                  {item.label}
                </Link>
              ))}
            </>
          )}
        </nav>
        <div>
          {data ? (
            <GroupForm key={group.id} group={group} initial={data.settings[group.id] ?? {}} onSaved={(settings) => setData({ ...data, settings })} />
          ) : (
            <div className="skeleton h-64" />
          )}
        </div>
      </div>
    </div>
  );
}
