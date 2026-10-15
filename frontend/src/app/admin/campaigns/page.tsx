"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { dateTime, money } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Campaign {
  id: number;
  name: string;
  subject: string;
  body: string;
  translations: Record<string, { subject: string; body: string }>;
  segment: string;
  coupon_kind: "percent" | "fixed" | "free_shipping" | null;
  coupon_value: number | null;
  coupon_expires_days: number | null;
  coupon_min_subtotal: number | null;
  status: "draft" | "sent";
  recipients: number;
  sent_at: string | null;
  created_at: string;
  coupons_issued: number;
  coupons_redeemed: number;
  revenue: number;
}

interface Form {
  id?: number;
  name: string;
  segment: string;
  subject: string;
  body: string;
  subject_es: string;
  body_es: string;
  subject_nl: string;
  body_nl: string;
  coupon: "" | "percent" | "fixed" | "free_shipping";
  value: string;
  days: string;
  minimum: string;
}

const EMPTY: Form = {
  name: "",
  segment: "subscribers",
  subject: "",
  body: "",
  subject_es: "",
  body_es: "",
  subject_nl: "",
  body_nl: "",
  coupon: "",
  value: "10",
  days: "14",
  minimum: "",
};

export default function AdminCampaigns() {
  const { push } = useToast();
  const [rows, setRows] = useState<Campaign[] | null>(null);
  const [segments, setSegments] = useState<{ key: string; label: string }[]>([]);
  const [form, setForm] = useState<Form | null>(null);
  const [audience, setAudience] = useState<number | null>(null);
  const [sending, setSending] = useState<Campaign | null>(null);
  const [sendAudience, setSendAudience] = useState<number | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    apiFetch<{ items: Campaign[]; segments: { key: string; label: string }[] }>("/admin/campaigns").then(
      (d) => {
        setRows(d.items);
        setSegments(d.segments);
      },
      (e) => setProblem(e.message),
    );
  }, []);
  useEffect(load, [load]);

  // How many people the chosen group reaches, shown while writing.
  useEffect(() => {
    if (!form) return;
    setAudience(null);
    apiFetch<{ count: number }>(`/admin/campaigns/audience?segment=${form.segment}`).then((a) => setAudience(a.count), () => setAudience(null));
  }, [form?.segment]); // eslint-disable-line react-hooks/exhaustive-deps

  function bodyOf(f: Form) {
    const translations: Record<string, { subject: string; body: string }> = {};
    if (f.subject_es.trim() && f.body_es.trim()) translations.es = { subject: f.subject_es, body: f.body_es };
    if (f.subject_nl.trim() && f.body_nl.trim()) translations.nl = { subject: f.subject_nl, body: f.body_nl };
    return {
      name: f.name.trim(),
      segment: f.segment,
      subject: f.subject,
      body: f.body,
      translations,
      coupon_kind: f.coupon || null,
      coupon_value: f.coupon && f.coupon !== "free_shipping" ? Number(f.value) : null,
      coupon_expires_days: f.coupon ? Number(f.days) || 14 : null,
      coupon_min_subtotal: f.coupon && f.minimum ? Number(f.minimum) : null,
    };
  }

  async function save(): Promise<Campaign | null> {
    if (!form) return null;
    setBusy(true);
    setProblem("");
    try {
      const saved = await apiFetch<Campaign>(form.id ? `/admin/campaigns/${form.id}` : "/admin/campaigns", {
        method: form.id ? "PUT" : "POST",
        body: JSON.stringify(bodyOf(form)),
      });
      setForm({ ...form, id: saved.id });
      load();
      return saved;
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Couldn't save the campaign");
      return null;
    } finally {
      setBusy(false);
    }
  }

  const label = (key: string) => segments.find((s) => s.key === key)?.label ?? key;

  const columns: Column<Campaign>[] = [
    {
      key: "name",
      header: "Campaign",
      cell: (c) => (
        <div>
          {c.status === "draft" ? (
            <button
              type="button"
              className="font-medium hover:underline"
              onClick={() => {
                setProblem("");
                setForm({
                  id: c.id,
                  name: c.name,
                  segment: c.segment,
                  subject: c.subject,
                  body: c.body,
                  subject_es: c.translations.es?.subject ?? "",
                  body_es: c.translations.es?.body ?? "",
                  subject_nl: c.translations.nl?.subject ?? "",
                  body_nl: c.translations.nl?.body ?? "",
                  coupon: c.coupon_kind ?? "",
                  value: String(c.coupon_value ?? 10),
                  days: String(c.coupon_expires_days ?? 14),
                  minimum: c.coupon_min_subtotal ? String(c.coupon_min_subtotal) : "",
                });
              }}
            >
              {c.name}
            </button>
          ) : (
            <span className="font-medium">{c.name}</span>
          )}
          <span className="block text-xs text-muted">
            {label(c.segment)} · “{c.subject}”
          </span>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (c) => (c.status === "sent" ? <Pill tone="success">Sent {c.sent_at ? dateTime(c.sent_at) : ""}</Pill> : <Pill tone="neutral">Draft</Pill>),
    },
    {
      key: "results",
      header: "Results",
      align: "right",
      cell: (c) =>
        c.status === "sent" ? (
          <span className="num text-sm">
            {c.recipients} sent
            {c.coupon_kind && (
              <span className="block text-xs text-muted">
                {c.coupons_redeemed} of {c.coupons_issued} codes used · {money(c.revenue)}
              </span>
            )}
          </span>
        ) : (
          <span className="text-sm text-muted">—</span>
        ),
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (c) =>
        c.status === "draft" ? (
          <Button
            size="sm"
            className="h-8"
            onClick={() => {
              setSending(c);
              setSendAudience(null);
              apiFetch<{ count: number }>(`/admin/campaigns/audience?segment=${c.segment}`).then((a) => setSendAudience(a.count), () => setSendAudience(null));
            }}
          >
            Send
            <span className="sr-only"> {c.name}</span>
          </Button>
        ) : null,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Email campaigns"
        description="One email to a group of subscribers, optionally with a personal discount code for each. Only people who asked for news receive it, and every email has an unsubscribe link."
        actions={
          <Button
            size="sm"
            onClick={() => {
              setProblem("");
              setForm({ ...EMPTY });
            }}
          >
            New campaign
          </Button>
        }
      />
      {problem && !form && (
        <Alert tone="danger" className="mb-4">
          {problem}
        </Alert>
      )}
      <Panel>
        <PanelHeader title="Campaigns" />
        <DataTable columns={columns} rows={rows} rowKey={(c) => c.id} caption="Email campaigns" empty="No campaigns yet. A thank-you note with a code for one-time buyers is a good first one." />
      </Panel>

      <Modal
        open={!!form}
        onClose={() => setForm(null)}
        title={form?.id ? "Edit campaign" : "New campaign"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              Close
            </Button>
            <Button
              variant="secondary"
              disabled={busy || !form?.name.trim() || !form?.subject.trim() || !form?.body.trim()}
              onClick={async () => {
                const saved = await save();
                if (!saved) return;
                try {
                  await apiFetch(`/admin/campaigns/${saved.id}/test`, { method: "POST" });
                  push({ title: "Test email sent", description: "Check your inbox." });
                } catch (e) {
                  setProblem(e instanceof Error ? e.message : "Couldn't send the test");
                }
              }}
            >
              Save and send me a test
            </Button>
            <Button
              disabled={busy || !form?.name.trim() || !form?.subject.trim() || !form?.body.trim()}
              onClick={async () => {
                const saved = await save();
                if (saved) {
                  push({ title: "Campaign saved", description: saved.name });
                  setForm(null);
                }
              }}
            >
              Save draft
            </Button>
          </>
        }
      >
        {form && (
          <div className="space-y-4">
            {problem && <Alert tone="danger">{problem}</Alert>}
            <Field label="Name" hint="For you, e.g. Autumn thank-you.">
              {(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={120} />}
            </Field>
            <Field label="Send to" hint={audience == null ? "Counting…" : `${audience} ${audience === 1 ? "person" : "people"} right now.`}>
              {(p) => (
                <Select {...p} value={form.segment} onChange={(e) => setForm({ ...form, segment: e.target.value })}>
                  {segments.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Subject">{(p) => <Input {...p} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} maxLength={200} />}</Field>
            <Field label="Message" hint="Plain text. Leave an empty line between paragraphs. The greeting, shop button and unsubscribe link are added for you.">
              {(p) => <Textarea {...p} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} maxLength={8000} className="min-h-40" />}
            </Field>
            <details className="rounded-lg border border-line p-3">
              <summary className="cursor-pointer text-sm font-medium">Spanish and Dutch versions (optional)</summary>
              <p className="mt-2 text-xs text-muted">Subscribers who signed up in Spanish or Dutch get these. Empty: they get the English text.</p>
              <div className="mt-3 space-y-3">
                <Field label="Subject in Spanish">{(p) => <Input {...p} value={form.subject_es} onChange={(e) => setForm({ ...form, subject_es: e.target.value })} maxLength={200} />}</Field>
                <Field label="Message in Spanish">{(p) => <Textarea {...p} value={form.body_es} onChange={(e) => setForm({ ...form, body_es: e.target.value })} maxLength={8000} />}</Field>
                <Field label="Subject in Dutch">{(p) => <Input {...p} value={form.subject_nl} onChange={(e) => setForm({ ...form, subject_nl: e.target.value })} maxLength={200} />}</Field>
                <Field label="Message in Dutch">{(p) => <Textarea {...p} value={form.body_nl} onChange={(e) => setForm({ ...form, body_nl: e.target.value })} maxLength={8000} />}</Field>
              </div>
            </details>
            <fieldset className="space-y-3 rounded-lg border border-line p-3">
              <legend className="px-1 text-sm font-medium">Personal discount code (optional)</legend>
              <Field label="Code for each recipient">
                {(p) => (
                  <Select {...p} value={form.coupon} onChange={(e) => setForm({ ...form, coupon: e.target.value as Form["coupon"] })}>
                    <option value="">No code</option>
                    <option value="percent">Percentage off</option>
                    <option value="fixed">Amount off</option>
                    <option value="free_shipping">Free shipping</option>
                  </Select>
                )}
              </Field>
              {form.coupon && (
                <div className="grid gap-3 sm:grid-cols-3">
                  {form.coupon !== "free_shipping" && (
                    <Field label={form.coupon === "percent" ? "Percent off" : "Dollars off"}>
                      {(p) => <Input {...p} type="number" min={1} value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />}
                    </Field>
                  )}
                  <Field label="Valid for (days)">{(p) => <Input {...p} type="number" min={1} max={365} value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} />}</Field>
                  <Field label="Minimum order (optional)">{(p) => <Input {...p} type="number" min={0} value={form.minimum} onChange={(e) => setForm({ ...form, minimum: e.target.value })} />}</Field>
                </div>
              )}
              <p className="text-xs text-muted">Each person gets their own single-use code that only works with their email address.</p>
            </fieldset>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!sending}
        title={`Send "${sending?.name}"?`}
        message={
          sendAudience == null
            ? "Counting the audience…"
            : `It goes to ${sendAudience} ${sendAudience === 1 ? "person" : "people"} (${label(sending?.segment ?? "")}). A campaign can only be sent once, and it can't be edited afterwards.`
        }
        confirmLabel="Send campaign"
        busy={busy || sendAudience == null}
        onConfirm={async () => {
          if (!sending) return;
          setBusy(true);
          try {
            const sent = await apiFetch<Campaign>(`/admin/campaigns/${sending.id}/send`, { method: "POST" });
            push({ title: "Campaign sent", description: `${sent.recipients} emails on their way` });
            setSending(null);
            load();
          } catch (e) {
            push({ title: "Not sent", description: e instanceof Error ? e.message : undefined, tone: "danger" });
          } finally {
            setBusy(false);
          }
        }}
        onCancel={() => setSending(null)}
      />
    </div>
  );
}
