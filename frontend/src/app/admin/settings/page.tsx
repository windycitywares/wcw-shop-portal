"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_URL, apiFetch } from "@/lib/client-api";
import type { StoreSettings } from "@/lib/types";
import { Icon } from "@/components/admin/ui/Icon";
import { ConfirmDialog } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { ShippingPanel } from "@/components/admin/settings/ShippingPanel";
import { TaxPanel } from "@/components/admin/settings/TaxPanel";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Draft {
  stripe_enabled: boolean;
  offline_enabled: boolean;
  offline_label: string;
  offline_instructions: string;
  welcome_enabled: boolean;
  welcome_kind: "percent" | "fixed";
  welcome_value: string;
  welcome_valid_days: string;
  welcome_min_subtotal: string;
  order_alert_email: string;
  low_stock_threshold: string;
}

const toDraft = (s: StoreSettings): Draft => ({
  stripe_enabled: s.stripe_enabled,
  offline_enabled: s.offline_enabled,
  offline_label: s.offline_label,
  offline_instructions: s.offline_instructions,
  welcome_enabled: s.welcome_enabled,
  welcome_kind: s.welcome_kind,
  welcome_value: String(Number(s.welcome_value)),
  welcome_valid_days: String(s.welcome_valid_days),
  welcome_min_subtotal: String(Number(s.welcome_min_subtotal)),
  order_alert_email: s.order_alert_email ?? "",
  low_stock_threshold: String(s.low_stock_threshold),
});

/** Only what changed, in the shapes the API wants. */
function changes(before: Draft, after: Draft) {
  const out: Record<string, unknown> = {};
  (Object.keys(after) as (keyof Draft)[]).forEach((key) => {
    if (before[key] === after[key]) return;
    const v = after[key];
    if (key === "order_alert_email") out[key] = (v as string).trim() || null;
    else if (key === "welcome_value" || key === "welcome_min_subtotal") out[key] = Number(v || 0);
    else if (key === "welcome_valid_days" || key === "low_stock_threshold") out[key] = Number(v || 0);
    else out[key] = typeof v === "string" ? v.trim() : v;
  });
  return out;
}

export default function AdminSettings() {
  const { push } = useToast();
  const [cfg, setCfg] = useState<StoreSettings | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);

  const apply = useCallback((s: StoreSettings) => {
    setCfg(s);
    setDraft(toDraft(s));
  }, []);

  useEffect(() => {
    apiFetch<StoreSettings>("/settings").then(apply, (e) => setError(e instanceof Error ? e.message : "Failed to load settings"));
  }, [apply]);

  const pending = useMemo(() => (cfg && draft ? changes(toDraft(cfg), draft) : {}), [cfg, draft]);
  const dirty = Object.keys(pending).length > 0;

  async function patch(body: Record<string, unknown>, done: string) {
    setBusy(true);
    setError("");
    try {
      apply(await apiFetch<StoreSettings>("/settings", { method: "PATCH", body: JSON.stringify(body) }));
      push({ title: done });
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't save");
      return false;
    } finally {
      setBusy(false);
    }
  }

  if (!cfg || !draft) {
    return (
      <div>
        <PageHeader title="Settings" />
        {error ? <Alert tone="danger">{error}</Alert> : <div className="skeleton h-64 w-full" aria-label="Loading settings" />}
      </div>
    );
  }

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => (d ? { ...d, [key]: value } : d));
  const blockers = cfg.readiness.filter((r) => r.required && !r.ok);
  const webhook = `${API_URL}/payments/stripe/webhook`;

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title="Settings" description="How the shop takes orders: when checkout is open, how people pay, shipping, tax and the emails you get." />
      {error && <Alert tone="danger">{error}</Alert>}

      <Panel>
        <PanelHeader
          title="Online checkout"
          description="While it is closed, shoppers can fill a cart but are pointed to your Etsy shop to buy."
          actions={<Pill tone={cfg.checkout_enabled ? "success" : "warning"}>{cfg.checkout_enabled ? "Open to customers" : "Closed"}</Pill>}
        />
        <PanelBody className="space-y-4">
          <ul className="space-y-2 text-sm">
            {cfg.readiness.map((item) => (
              <li key={item.id} className="flex items-start gap-2">
                <Icon name={item.ok ? "check" : "alert"} className={`mt-0.5 size-4 ${item.ok ? "text-success" : item.required ? "text-danger" : "text-warning"}`} strokeWidth={2} />
                <span>
                  {item.text}
                  {!item.ok && <span className="text-muted"> — {item.required ? "needed before you open checkout" : "recommended"}</span>}
                </span>
              </li>
            ))}
          </ul>
          {cfg.test_payments_available && (
            <p className="text-sm text-muted">This is a development copy of the shop, so a &ldquo;Test payment&rdquo; option is available at checkout. It never charges anyone and disappears on the live site.</p>
          )}
          {cfg.checkout_enabled ? (
            <Button variant="secondary" size="sm" className="h-9" onClick={() => setConfirmClose(true)} disabled={busy}>
              Close checkout
            </Button>
          ) : (
            <div>
              <Button size="sm" className="h-9" disabled={busy || blockers.length > 0} onClick={() => patch({ checkout_enabled: true }, "Checkout is open")}>
                Open checkout
              </Button>
              {blockers.length > 0 && <p className="mt-2 text-xs text-muted">Finish the items marked above first.</p>}
            </div>
          )}
        </PanelBody>
      </Panel>

      <form
        className="space-y-6"
        onSubmit={async (e) => {
          e.preventDefault();
          if (dirty) await patch(pending, "Settings saved");
        }}
      >
        <Panel>
          <PanelHeader title="Ways to pay" description="Customers choose from the ones that are switched on." />
          <PanelBody className="space-y-6">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input type="checkbox" checked={draft.stripe_enabled} onChange={(e) => set("stripe_enabled", e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
                  Credit and debit cards (Stripe)
                </label>
                <Pill tone={cfg.stripe_configured ? "success" : "warning"}>{cfg.stripe_configured ? "Stripe connected" : "Stripe not connected yet"}</Pill>
              </div>
              <p className="text-sm text-muted">
                Customers pay on Stripe&apos;s own secure page, so card numbers never reach this site.
                {!cfg.stripe_configured && " Connecting Stripe needs two secret keys added to the server; ask your developer or follow docs/DEPLOYMENT.md."}
              </p>
              <p className="text-sm text-muted">
                Webhook address to give Stripe: <code className="break-all rounded bg-sand px-1.5 py-0.5 text-xs">{webhook}</code>
              </p>
            </div>

            <div className="space-y-3 border-t border-line pt-5">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input type="checkbox" checked={draft.offline_enabled} onChange={(e) => set("offline_enabled", e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
                Pay by invoice (check or bank transfer)
              </label>
              {draft.offline_enabled && (
                <div className="space-y-4">
                  <Field label="Name at checkout">{(p) => <Input {...p} value={draft.offline_label} onChange={(e) => set("offline_label", e.target.value)} required maxLength={80} />}</Field>
                  <Field label="How to pay" hint="Shown to the customer after they order and in their email. Say who to pay and where.">
                    {(p) => <Textarea {...p} value={draft.offline_instructions} onChange={(e) => set("offline_instructions", e.target.value)} maxLength={2000} />}
                  </Field>
                </div>
              )}
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Welcome offer" description="A one-time code emailed to people who join the newsletter. It works on a first order only." />
          <PanelBody className="space-y-4">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" checked={draft.welcome_enabled} onChange={(e) => set("welcome_enabled", e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
              Send a welcome code
            </label>
            {draft.welcome_enabled && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Kind of discount">
                  {(p) => (
                    <Select {...p} value={draft.welcome_kind} onChange={(e) => set("welcome_kind", e.target.value as "percent" | "fixed")}>
                      <option value="percent">Percent off</option>
                      <option value="fixed">Amount off</option>
                    </Select>
                  )}
                </Field>
                <Field label={draft.welcome_kind === "percent" ? "Percent (1–100)" : "Amount off (USD)"}>
                  {(p) => <Input {...p} type="number" inputMode="decimal" step="0.5" min="0.5" required value={draft.welcome_value} onChange={(e) => set("welcome_value", e.target.value)} />}
                </Field>
                <Field label="Valid for (days)">
                  {(p) => <Input {...p} type="number" inputMode="numeric" step="1" min="1" max="365" required value={draft.welcome_valid_days} onChange={(e) => set("welcome_valid_days", e.target.value)} />}
                </Field>
                <Field label="Minimum spend (USD)" hint="0 = no minimum.">
                  {(p) => <Input {...p} type="number" inputMode="decimal" step="0.01" min="0" required value={draft.welcome_min_subtotal} onChange={(e) => set("welcome_min_subtotal", e.target.value)} />}
                </Field>
              </div>
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Emails and stock" />
          <PanelBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Send new-order emails to" hint="Empty = the shop's contact address.">
              {(p) => <Input {...p} type="email" value={draft.order_alert_email} onChange={(e) => set("order_alert_email", e.target.value)} maxLength={254} />}
            </Field>
            <Field label="Call it “low stock” at or below" hint="Used on the dashboard and in inventory reports.">
              {(p) => <Input {...p} type="number" inputMode="numeric" step="1" min="0" max="1000" required value={draft.low_stock_threshold} onChange={(e) => set("low_stock_threshold", e.target.value)} />}
            </Field>
          </PanelBody>
        </Panel>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={!dirty || busy}>
            {busy ? "Saving…" : "Save settings"}
          </Button>
          {dirty && !busy && <p className="text-sm text-muted">You have unsaved changes.</p>}
        </div>
      </form>

      <ShippingPanel />
      <TaxPanel />

      <ConfirmDialog
        open={confirmClose}
        title="Close online checkout?"
        message="Customers keep their carts but can't place orders until you open checkout again. Orders already placed are not affected."
        confirmLabel="Close checkout"
        busy={busy}
        onCancel={() => setConfirmClose(false)}
        onConfirm={async () => {
          if (await patch({ checkout_enabled: false }, "Checkout is closed")) setConfirmClose(false);
        }}
      />
    </div>
  );
}
