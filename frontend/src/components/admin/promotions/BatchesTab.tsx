"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, downloadFile } from "@/lib/client-api";
import type { Campaign } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { Modal } from "@/components/admin/ui/Modal";
import { Panel } from "@/components/admin/ui/Panel";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { day } from "./format";
import { EMPTY_RULES, RulesFields, rulesPayload, type RulesState } from "./RulesFields";

interface Generated {
  campaign: string;
  count: number;
  codes: string[];
}

/** Batches of single-use codes (for a mailing or a printed flyer) and one-off personal codes sent by email. */
export function BatchesTab() {
  const { push } = useToast();
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [error, setError] = useState("");
  const [making, setMaking] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<Generated | null>(null);

  const load = useCallback(async () => {
    try {
      setCampaigns(await apiFetch<Campaign[]>("/promotions/campaigns"));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load batches");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function download(campaign: string) {
    try {
      await downloadFile(`/promotions/campaigns/${encodeURIComponent(campaign)}/codes.csv`, `codes-${campaign.replace(/[^A-Za-z0-9_-]/g, "_")}.csv`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The download didn't work");
    }
  }

  const columns: Column<Campaign>[] = [
    { key: "name", header: "Batch", cell: (c) => <span className="font-medium">{c.campaign}</span> },
    { key: "codes", header: "Codes", align: "right", cell: (c) => <span className="num">{c.codes}</span> },
    {
      key: "used",
      header: "Used",
      align: "right",
      cell: (c) => (
        <span className="num">
          {c.used}
          <span className="text-muted"> ({c.codes > 0 ? Math.round((c.used / c.codes) * 100) : 0}%)</span>
        </span>
      ),
    },
    { key: "given", header: "Discount given", align: "right", hide: "sm", cell: (c) => <span className="num">{formatPrice(c.discount_given, "USD")}</span> },
    { key: "made", header: "Made", hide: "md", cell: (c) => <span className="text-muted">{day(c.created_at)}</span> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (c) => (
        <Button size="sm" variant="ghost" className="h-8" onClick={() => download(c.campaign)}>
          <Icon name="download" className="size-4" />
          Download codes<span className="sr-only"> for {c.campaign}</span>
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {error && <Alert tone="danger">{error}</Alert>}
      {result && (
        <Alert tone="success">
          <p className="font-medium">
            Made {result.count} {result.count === 1 ? "code" : "codes"} in batch “{result.campaign}”.
          </p>
          <p className="mt-1 font-mono text-xs">{result.codes.slice(0, 6).join("  ")}{result.codes.length > 6 ? "  …" : ""}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" className="h-8" onClick={() => download(result.campaign)}>
              <Icon name="download" className="size-4" />
              Download all codes (CSV)
            </Button>
            <Button
              size="sm"
              variant="secondary"
              className="h-8"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(result.codes.join("\n"));
                  push({ title: "Codes copied" });
                } catch {
                  push({ tone: "danger", title: "Couldn't copy", description: "Download the CSV instead." });
                }
              }}
            >
              <Icon name="copy" className="size-4" />
              Copy codes
            </Button>
          </div>
        </Alert>
      )}
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <p className="max-w-xl text-sm text-muted">Make many single-use codes at once for a mailing, a flyer or a QR code, or send one personal code to a customer by email.</p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" className="h-9" onClick={() => setSending(true)}>
              <Icon name="mail" className="size-4" />
              Send a personal code
            </Button>
            <Button size="sm" className="h-9" onClick={() => setMaking(true)}>
              <Icon name="plus" className="size-4" />
              Make a batch
            </Button>
          </div>
        </div>
        <DataTable caption="Batches of codes" columns={columns} rows={campaigns} rowKey={(c) => c.campaign} empty="No batches yet." />
      </Panel>

      <BatchForm
        open={making}
        onClose={() => setMaking(false)}
        onDone={async (r) => {
          setMaking(false);
          setResult(r);
          await load();
        }}
      />
      <PersonalForm
        open={sending}
        onClose={() => setSending(false)}
        onDone={async (email) => {
          setSending(false);
          push({ title: "Code sent", description: email });
        }}
      />
    </div>
  );
}

function BatchForm({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (r: Generated) => void | Promise<void> }) {
  const [campaign, setCampaign] = useState("");
  const [count, setCount] = useState("50");
  const [prefix, setPrefix] = useState("");
  const [uses, setUses] = useState("1");
  const [rules, setRules] = useState<RulesState>(EMPTY_RULES);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setCampaign("");
    setCount("50");
    setPrefix("");
    setUses("1");
    setRules(EMPTY_RULES);
    setError("");
    setBusy(false);
  }, [open]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const made = await apiFetch<Generated>("/promotions/coupons/generate", {
        method: "POST",
        body: JSON.stringify({ ...rulesPayload(rules), campaign: campaign.trim(), count: Number(count), prefix: prefix.trim(), usage_limit: Number(uses) }),
      });
      await onDone(made);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not make the codes");
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Make a batch of codes"
      description="Each code is random, so nobody can guess one. Download the list when it's ready."
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="batch-form" size="sm" className="h-9" disabled={busy}>
            {busy ? "Making codes…" : "Make codes"}
          </Button>
        </>
      }
    >
      <form id="batch-form" onSubmit={submit} className="space-y-5">
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Batch name" hint="So you can find these later, e.g. October flyer.">
            {(p) => <Input {...p} value={campaign} onChange={(e) => setCampaign(e.target.value)} required maxLength={80} />}
          </Field>
          <Field label="How many codes" hint="Up to 500 at a time.">
            {(p) => <Input {...p} type="number" inputMode="numeric" min="1" max="500" step="1" required value={count} onChange={(e) => setCount(e.target.value)} />}
          </Field>
          <Field label="Start every code with (optional)" hint="Letters and numbers, e.g. FALL.">
            {(p) => <Input {...p} value={prefix} onChange={(e) => setPrefix(e.target.value.toUpperCase())} maxLength={12} pattern="[A-Za-z0-9]*" className="font-mono uppercase" autoComplete="off" />}
          </Field>
          <Field label="Times each code can be used" hint="1 means one customer per code.">
            {(p) => <Input {...p} type="number" inputMode="numeric" min="1" step="1" required value={uses} onChange={(e) => setUses(e.target.value)} />}
          </Field>
        </div>
        <RulesFields value={rules} onChange={setRules} />
      </form>
    </Modal>
  );
}

function PersonalForm({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (email: string) => void | Promise<void> }) {
  const [email, setEmail] = useState("");
  const [locale, setLocale] = useState("en");
  const [message, setMessage] = useState("");
  const [validDays, setValidDays] = useState("30");
  const [rules, setRules] = useState<RulesState>(EMPTY_RULES);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setEmail("");
    setLocale("en");
    setMessage("");
    setValidDays("30");
    setRules(EMPTY_RULES);
    setError("");
    setBusy(false);
  }, [open]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiFetch("/promotions/coupons/send", {
        method: "POST",
        body: JSON.stringify({ ...rulesPayload(rules), email: email.trim(), locale, message: message.trim() || null, valid_days: validDays.trim() ? Number(validDays) : null }),
      });
      await onDone(email.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the code");
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Send a personal code"
      description="Makes a code that only this email address can use, and emails it to them."
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="personal-form" size="sm" className="h-9" disabled={busy}>
            {busy ? "Sending…" : "Send code"}
          </Button>
        </>
      }
    >
      <form id="personal-form" onSubmit={submit} className="space-y-5">
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Customer's email" className="sm:col-span-2">
            {(p) => <Input {...p} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} autoComplete="off" />}
          </Field>
          <Field label="Email language">
            {(p) => (
              <Select {...p} value={locale} onChange={(e) => setLocale(e.target.value)}>
                <option value="en">English</option>
                <option value="es">Español</option>
                <option value="nl">Nederlands</option>
              </Select>
            )}
          </Field>
        </div>
        <Field label="A personal line (optional)" hint="Shown in the email, e.g. Thank you for trusting us with your pet's urn.">
          {(p) => <Textarea {...p} value={message} onChange={(e) => setMessage(e.target.value)} maxLength={500} className="min-h-20" />}
        </Field>
        <Field label="Valid for (days)" hint="Counted from today. Ignored if you set an end date below. Empty = no end date.">
          {(p) => <Input {...p} type="number" inputMode="numeric" min="1" max="730" step="1" value={validDays} onChange={(e) => setValidDays(e.target.value)} className="max-w-32" />}
        </Field>
        <RulesFields value={rules} onChange={setRules} />
      </form>
    </Modal>
  );
}
