"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { downloadFile } from "../download";
import { dateTime, money } from "../charts/format";
import { DataTable, type Column } from "../ui/DataTable";
import { ConfirmDialog, Modal } from "../ui/Modal";
import { Pagination } from "../ui/Pagination";
import { Panel, PanelHeader } from "../ui/Panel";
import { useToast } from "../ui/Toast";
import { IconButton, RowActions } from "@/components/admin/ui/IconButton";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { Schedule, StatusPill, TargetPicker, fromLocalInput, shortDate, toLocalInput, type Targets } from "./common";

export interface Coupon {
  id: number;
  code: string;
  name: string | null;
  kind: "percent" | "fixed" | "free_shipping";
  value: number;
  max_discount: number | null;
  min_subtotal: number;
  scope: "order" | "category" | "products";
  category_ids: number[];
  product_ids: number[];
  exclude_sale_items: boolean;
  starts_at: string | null;
  expires_at: string | null;
  usage_limit: number | null;
  per_customer_limit: number | null;
  first_order_only: boolean;
  assigned_email: string | null;
  campaign: string | null;
  source: string;
  stackable: boolean;
  is_active: boolean;
  used_count: number;
  created_at: string;
  status: string;
}

interface CouponDetail extends Coupon {
  redemptions: { order_id: number; order_number: string; email: string; amount: number; created_at: string }[];
  revenue: number;
}

const PAGE_SIZE = 25;
const SOURCE: Record<string, string> = {
  manual: "Made by hand",
  bulk: "Bulk batch",
  welcome: "Welcome offer",
  abandoned_cart: "Cart reminder",
  campaign: "Email campaign",
};

export function describeCoupon(c: Pick<Coupon, "kind" | "value" | "min_subtotal">): string {
  const what = c.kind === "percent" ? `${c.value}% off` : c.kind === "fixed" ? `${money(c.value)} off` : "Free shipping";
  return c.min_subtotal > 0 ? `${what} orders over ${money(c.min_subtotal)}` : what;
}

/** Terms shared by single and bulk coupons. */
interface Terms {
  name: string;
  kind: Coupon["kind"];
  value: string;
  max_discount: string;
  min_subtotal: string;
  targets: Targets;
  exclude_sale_items: boolean;
  starts: string;
  expires: string;
  usage_limit: string;
  per_customer_limit: string;
  first_order_only: boolean;
  campaign: string;
  stackable: boolean;
}

const EMPTY_TERMS: Terms = {
  name: "",
  kind: "percent",
  value: "10",
  max_discount: "",
  min_subtotal: "",
  targets: { scope: "order", category_ids: [], product_ids: [] },
  exclude_sale_items: false,
  starts: "",
  expires: "",
  usage_limit: "",
  per_customer_limit: "1",
  first_order_only: false,
  campaign: "",
  stackable: false,
};

const num = (v: string) => (v.trim() === "" ? null : Number(v));

function termsBody(t: Terms) {
  return {
    name: t.name.trim() || null,
    kind: t.kind,
    value: t.kind === "free_shipping" ? 0 : Number(t.value),
    max_discount: t.kind === "percent" ? num(t.max_discount) : null,
    min_subtotal: num(t.min_subtotal) ?? 0,
    scope: t.targets.scope,
    category_ids: t.targets.category_ids,
    product_ids: t.targets.product_ids,
    exclude_sale_items: t.exclude_sale_items,
    starts_at: fromLocalInput(t.starts),
    expires_at: fromLocalInput(t.expires),
    usage_limit: num(t.usage_limit),
    per_customer_limit: num(t.per_customer_limit),
    first_order_only: t.first_order_only,
    campaign: t.campaign.trim() || null,
    stackable: t.stackable,
    is_active: true,
  };
}

function TermsFields({ value: t, onChange, showCampaign = true }: { value: Terms; onChange: (t: Terms) => void; showCampaign?: boolean }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Discount">
          {(p) => (
            <Select {...p} value={t.kind} onChange={(e) => onChange({ ...t, kind: e.target.value as Terms["kind"] })}>
              <option value="percent">Percentage off</option>
              <option value="fixed">Amount off the order</option>
              <option value="free_shipping">Free shipping</option>
            </Select>
          )}
        </Field>
        {t.kind !== "free_shipping" && (
          <Field label={t.kind === "percent" ? "Percent off" : "Dollars off"} error={t.kind === "percent" && Number(t.value) > 100 ? "At most 100%" : undefined}>
            {(p) => <Input {...p} type="number" min={0.01} step={t.kind === "percent" ? 1 : 0.01} value={t.value} onChange={(e) => onChange({ ...t, value: e.target.value })} />}
          </Field>
        )}
        {t.kind === "percent" && (
          <Field label="Most it can take off (optional)">
            {(p) => <Input {...p} type="number" min={1} step={0.01} value={t.max_discount} onChange={(e) => onChange({ ...t, max_discount: e.target.value })} />}
          </Field>
        )}
        <Field label="Minimum order (optional)" hint="Items after sale prices.">
          {(p) => <Input {...p} type="number" min={0} step={0.01} value={t.min_subtotal} onChange={(e) => onChange({ ...t, min_subtotal: e.target.value })} />}
        </Field>
      </div>
      {t.kind !== "free_shipping" && <TargetPicker value={t.targets} onChange={(targets) => onChange({ ...t, targets })} everythingScope="order" />}
      <Schedule starts={t.starts} ends={t.expires} endLabel="Expires" onChange={(starts, expires) => onChange({ ...t, starts, expires })} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Total uses (optional)" hint="Empty: unlimited.">
          {(p) => <Input {...p} type="number" min={1} value={t.usage_limit} onChange={(e) => onChange({ ...t, usage_limit: e.target.value })} />}
        </Field>
        <Field label="Uses per customer (optional)">
          {(p) => <Input {...p} type="number" min={1} value={t.per_customer_limit} onChange={(e) => onChange({ ...t, per_customer_limit: e.target.value })} />}
        </Field>
      </div>
      {showCampaign && (
        <Field label="Campaign (optional)" hint="A label to group and report on codes, e.g. instagram-fall.">
          {(p) => <Input {...p} value={t.campaign} onChange={(e) => onChange({ ...t, campaign: e.target.value })} maxLength={80} />}
        </Field>
      )}
      <fieldset className="space-y-2 text-sm">
        <legend className="sr-only">Rules</legend>
        {(
          [
            ["first_order_only", "Only for a customer's first order"],
            ["exclude_sale_items", "Not on items that are already on sale"],
            ["stackable", "Can be combined with automatic offers"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2">
            <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={t[key]} onChange={(e) => onChange({ ...t, [key]: e.target.checked })} />
            {label}
          </label>
        ))}
      </fieldset>
    </div>
  );
}

export function CouponsTab() {
  const { push } = useToast();
  const [status, setStatus] = useState("");
  const [campaign, setCampaign] = useState("");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: Coupon[]; total: number; campaigns: string[] } | null>(null);
  const [mode, setMode] = useState<"single" | "bulk" | null>(null);
  const [editing, setEditing] = useState<Coupon | null>(null);
  const [terms, setTerms] = useState<Terms>(EMPTY_TERMS);
  const [code, setCode] = useState("");
  const [email, setEmail] = useState("");
  const [bulk, setBulk] = useState({ count: "50", prefix: "", emails: "" });
  const [result, setResult] = useState<{ created: number; campaign: string; sample: string[] } | null>(null);
  const [detail, setDetail] = useState<CouponDetail | null>(null);
  const [deleting, setDeleting] = useState<Coupon | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  const query = useCallback(() => {
    const p = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    if (status) p.set("status", status);
    if (campaign) p.set("campaign", campaign);
    return p;
  }, [q, status, campaign, page]);

  const load = useCallback(() => {
    apiFetch<{ items: Coupon[]; total: number; campaigns: string[] }>(`/admin/promotions/coupons?${query()}`).then(setData, (e) => setProblem(e.message));
  }, [query]);
  useEffect(load, [load]);

  function openSingle(c?: Coupon) {
    setProblem("");
    setEditing(c ?? null);
    setCode(c?.code ?? "");
    setEmail(c?.assigned_email ?? "");
    setTerms(
      c
        ? {
            name: c.name ?? "",
            kind: c.kind,
            value: String(c.value),
            max_discount: c.max_discount != null ? String(c.max_discount) : "",
            min_subtotal: c.min_subtotal ? String(c.min_subtotal) : "",
            targets: { scope: c.scope, category_ids: c.category_ids, product_ids: c.product_ids },
            exclude_sale_items: c.exclude_sale_items,
            starts: toLocalInput(c.starts_at),
            expires: toLocalInput(c.expires_at),
            usage_limit: c.usage_limit != null ? String(c.usage_limit) : "",
            per_customer_limit: c.per_customer_limit != null ? String(c.per_customer_limit) : "",
            first_order_only: c.first_order_only,
            campaign: c.campaign ?? "",
            stackable: c.stackable,
          }
        : { ...EMPTY_TERMS },
    );
    setMode("single");
  }

  async function saveSingle() {
    setBusy(true);
    setProblem("");
    try {
      const body = { ...termsBody(terms), code: code.trim() || null, assigned_email: email.trim() || null };
      const saved = await apiFetch<Coupon>(editing ? `/admin/promotions/coupons/${editing.id}` : "/admin/promotions/coupons", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(body),
      });
      push({ title: editing ? "Coupon saved" : "Coupon created", description: saved.code });
      setMode(null);
      load();
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Couldn't save the coupon");
    } finally {
      setBusy(false);
    }
  }

  async function saveBulk() {
    setBusy(true);
    setProblem("");
    const emails = bulk.emails
      .split(/[\s,;]+/)
      .map((e) => e.trim())
      .filter(Boolean);
    try {
      const body = {
        ...termsBody(terms),
        campaign: terms.campaign.trim(),
        count: Number(bulk.count) || 1,
        prefix: bulk.prefix,
        emails,
        usage_limit: num(terms.usage_limit) ?? 1,
      };
      const res = await apiFetch<{ created: number; campaign: string; sample: string[] }>("/admin/promotions/coupons/bulk", { method: "POST", body: JSON.stringify(body) });
      setResult(res);
      setMode(null);
      setCampaign(res.campaign);
      setPage(1);
      push({ title: `${res.created} codes created`, description: res.campaign });
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Couldn't create the codes");
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<Coupon>[] = [
    {
      key: "code",
      header: "Code",
      cell: (c) => (
        <div>
          <button
            type="button"
            className="font-mono font-medium hover:underline"
            onClick={() => apiFetch<CouponDetail>(`/admin/promotions/coupons/${c.id}`).then(setDetail, (e) => setProblem(e.message))}
          >
            {c.code}
          </button>
          <span className="block text-xs text-muted">{describeCoupon(c)}</span>
        </div>
      ),
    },
    {
      key: "who",
      header: "For",
      hide: "md",
      cell: (c) => (
        <span className="text-sm">
          {c.assigned_email ?? "Anyone"}
          <span className="block text-xs text-muted">
            {SOURCE[c.source] ?? c.source}
            {c.campaign ? ` · ${c.campaign}` : ""}
          </span>
        </span>
      ),
    },
    {
      key: "uses",
      header: "Used",
      align: "right",
      cell: (c) => (
        <span className="num text-sm">
          {c.used_count}
          {c.usage_limit != null ? ` / ${c.usage_limit}` : ""}
        </span>
      ),
    },
    { key: "expires", header: "Expires", hide: "lg", cell: (c) => <span className="text-sm text-muted">{c.expires_at ? shortDate(c.expires_at) : "Never"}</span> },
    { key: "status", header: "Status", cell: (c) => <StatusPill status={c.status} /> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (c) => (
        <RowActions>
          <IconButton icon="edit" label={`Edit ${c.code}`} onClick={() => openSingle(c)} />
          <IconButton icon={c.used_count > 0 ? "clock" : "trash"} tone="danger" label={`${c.used_count > 0 ? "Pause" : "Delete"} ${c.code}`} onClick={() => setDeleting(c)} />
        </RowActions>
      ),
    },
  ];

  return (
    <Panel>
      <PanelHeader
        title="Coupons"
        description="Codes shoppers type at checkout. One code per order; the cart explains why a code doesn't apply."
        actions={
          <>
            <Button size="sm" variant="secondary" onClick={() => downloadFile(`/admin/promotions/coupons/export.csv?${query()}`, "wcw-coupons.csv").catch((e) => setProblem(e.message))}>
              Export CSV
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setProblem("");
                setTerms({ ...EMPTY_TERMS, usage_limit: "1" });
                setBulk({ count: "50", prefix: "", emails: "" });
                setMode("bulk");
              }}
            >
              Generate codes
            </Button>
            <Button size="sm" onClick={() => openSingle()}>
              New coupon
            </Button>
          </>
        }
      />
      {problem && !mode && (
        <div className="px-5 pt-4">
          <Alert tone="danger">{problem}</Alert>
        </div>
      )}
      {result && (
        <div className="px-5 pt-4">
          <Alert tone="success">
            {result.created} codes created for “{result.campaign}”, e.g. <span className="font-mono">{result.sample.join(", ")}</span>. Use Export CSV to download them all.
          </Alert>
        </div>
      )}
      <form
        className="flex flex-wrap items-center gap-3 px-5 py-3"
        onSubmit={(e) => {
          e.preventDefault();
          setQ(draft.trim());
          setPage(1);
        }}
      >
        <label htmlFor="coupon-search" className="sr-only">
          Search coupons
        </label>
        <Input id="coupon-search" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Code, name or email" className="h-9 max-w-xs" />
        <Button type="submit" size="sm" variant="secondary">
          Search
        </Button>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">Status</span>
          <select className="h-9 rounded-lg border border-line bg-surface px-2" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">Any</option>
            <option value="active">Running</option>
            <option value="scheduled">Scheduled</option>
            <option value="expired">Expired</option>
            <option value="used_up">Used up</option>
            <option value="paused">Paused</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">Campaign</span>
          <select className="h-9 max-w-[12rem] rounded-lg border border-line bg-surface px-2" value={campaign} onChange={(e) => { setCampaign(e.target.value); setPage(1); }}>
            <option value="">Any</option>
            {(data?.campaigns ?? []).map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </form>
      <DataTable columns={columns} rows={data?.items ?? null} rowKey={(c) => c.id} caption="Coupons" empty="No coupons match. Create one, or generate a batch for a campaign." />
      {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} className="px-5 py-3" />}

      <Modal
        open={mode === "single"}
        onClose={() => setMode(null)}
        title={editing ? `Edit ${editing.code}` : "New coupon"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setMode(null)}>
              Cancel
            </Button>
            <Button disabled={busy} onClick={saveSingle}>
              {editing ? "Save coupon" : "Create coupon"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {problem && <Alert tone="danger">{problem}</Alert>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Code" hint={editing?.used_count ? "Used codes can't be renamed." : "Empty: we make an unguessable one."}>
              {(p) => <Input {...p} value={code} disabled={!!editing?.used_count} onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={40} className="font-mono uppercase" />}
            </Field>
            <Field label="Only for this email (optional)">{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
          </div>
          <Field label="Name (optional)" hint="For you, e.g. Instagram fall post.">
            {(p) => <Input {...p} value={terms.name} onChange={(e) => setTerms({ ...terms, name: e.target.value })} maxLength={120} />}
          </Field>
          <TermsFields value={terms} onChange={setTerms} />
        </div>
      </Modal>

      <Modal
        open={mode === "bulk"}
        onClose={() => setMode(null)}
        title="Generate codes"
        description="Many single-use codes for a campaign, or one personal code for each email address. Codes avoid look-alike characters (0/O, 1/I)."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setMode(null)}>
              Cancel
            </Button>
            <Button disabled={busy || !terms.campaign.trim()} onClick={saveBulk}>
              Generate codes
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {problem && <Alert tone="danger">{problem}</Alert>}
          <Field label="Campaign" hint="Required: groups the codes for reports and export, e.g. trade-partners.">
            {(p) => <Input {...p} value={terms.campaign} onChange={(e) => setTerms({ ...terms, campaign: e.target.value })} maxLength={80} />}
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="How many codes" hint="Ignored when emails are given below.">
              {(p) => <Input {...p} type="number" min={1} max={5000} value={bulk.count} onChange={(e) => setBulk({ ...bulk, count: e.target.value })} />}
            </Field>
            <Field label="Prefix (optional)" hint="Letters and digits, e.g. FALL.">
              {(p) => <Input {...p} value={bulk.prefix} onChange={(e) => setBulk({ ...bulk, prefix: e.target.value.toUpperCase() })} maxLength={12} className="font-mono uppercase" />}
            </Field>
          </div>
          <Field label="Personal codes for these emails (optional)" hint="One per line or separated by commas. Each person gets their own code that only works with their email.">
            {(p) => <Textarea {...p} value={bulk.emails} onChange={(e) => setBulk({ ...bulk, emails: e.target.value })} className="min-h-24 font-mono text-xs" />}
          </Field>
          <TermsFields value={terms} onChange={setTerms} showCampaign={false} />
        </div>
      </Modal>

      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail ? `Coupon ${detail.code}` : ""} description={detail ? describeCoupon(detail) : undefined} size="lg">
        {detail && (
          <div className="space-y-4 text-sm">
            <p>
              Used <span className="num font-medium">{detail.used_count}</span>
              {detail.usage_limit != null ? ` of ${detail.usage_limit}` : ""} times · orders with this code total <span className="num font-medium">{money(detail.revenue)}</span> (paid, minus refunds).
            </p>
            {detail.redemptions.length === 0 ? (
              <p className="text-muted">Not used yet.</p>
            ) : (
              <ul className="divide-y divide-line rounded-lg border border-line">
                {detail.redemptions.map((r) => (
                  <li key={r.order_id} className="flex justify-between gap-3 px-3 py-2">
                    <span>
                      <a href={`/admin/orders/${r.order_id}`} className="num font-medium text-accent underline underline-offset-4">
                        {r.order_number}
                      </a>
                      <span className="block text-xs text-muted">
                        {r.email} · {dateTime(r.created_at)}
                      </span>
                    </span>
                    <span className="num">−{money(r.amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title={deleting?.used_count ? `Pause ${deleting?.code}?` : `Delete ${deleting?.code}?`}
        message={deleting?.used_count ? "This code was used, so it's paused instead of deleted: past orders keep their history." : "The code stops working straight away."}
        confirmLabel={deleting?.used_count ? "Pause coupon" : "Delete coupon"}
        tone="danger"
        onConfirm={async () => {
          if (!deleting) return;
          try {
            const res = await apiFetch<{ result: string }>(`/admin/promotions/coupons/${deleting.id}`, { method: "DELETE" });
            push({ title: res.result === "paused" ? "Coupon paused" : "Coupon deleted", description: deleting.code });
            setDeleting(null);
            load();
          } catch (e) {
            push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
          }
        }}
        onCancel={() => setDeleting(null)}
      />
    </Panel>
  );
}
