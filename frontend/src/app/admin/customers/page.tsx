"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { downloadFile } from "@/components/admin/download";
import { dateTime, money, timeAgo } from "@/components/admin/charts/format";
import { ORDER_STATUS } from "@/components/admin/reports";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { useToast } from "@/components/admin/ui/Toast";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { Tabs } from "@/components/admin/ui/Tabs";
import { AccountsAdmin } from "@/components/admin/users/AccountsAdmin";
import { useAuth } from "@/lib/auth";

interface Customer {
  email: string;
  name: string | null;
  orders: number;
  revenue: number;
  average_order: number;
  first_order_at: string | null;
  last_order_at: string | null;
  segment: string;
  subscribed: boolean;
  has_account: boolean;
  account_id: number | null;
  account_active: boolean | null;
  joined_at: string | null;
}

interface Segment {
  key: string;
  label: string;
  help: string;
  customers: number;
  revenue: number;
}

interface CustomerList {
  items: Customer[];
  total: number;
  segments: Segment[];
  total_customers: number;
  accounts_without_orders: number;
  subscribers_without_orders: number;
}

interface CustomerDetail {
  summary: Customer;
  refunded: number;
  orders: { id: number; number: string; status: string; payment_status: string; grand_total: number; refunded_total: number; coupon_code: string | null; placed_at: string | null }[];
  coupons: { code: string; kind: string; value: number; status: string; source: string; expires_at: string | null }[];
  subscription: { status: string; source: string; since: string } | null;
  reviews: number;
  account_role: string | null;
}

const SEGMENT_TONE: Record<string, Tone> = {
  vip: "accent",
  loyal: "success",
  active: "success",
  new: "info",
  needs_nudge: "warning",
  at_risk: "danger",
  lapsed: "neutral",
  signed_up: "info",
};
const ACCOUNT_FILTERS = [
  { id: "all", label: "Everyone" },
  { id: "account", label: "Has an account" },
  { id: "guest", label: "Guest checkout" },
  { id: "disabled", label: "Account switched off" },
];
const SORTS = [
  { id: "revenue", label: "Most spent" },
  { id: "orders", label: "Most orders" },
  { id: "recent", label: "Ordered most recently" },
  { id: "oldest", label: "Longest since last order" },
  { id: "name", label: "Name" },
  { id: "joined", label: "Signed up most recently" },
];
const PAGE_SIZE = 25;

type View = "buyers" | "accounts";

/** One place for customers. "Buyers" are people who paid (guest checkout included), grouped by how they buy;
 *  "Accounts" are the shop logins, where an account is edited or switched off. */
export default function AdminCustomers() {
  const { can } = useAuth();
  const canAccounts = can("users:manage");
  const [view, setView] = useState<View>("buyers");
  const [accountQuery, setAccountQuery] = useState("");
  // /admin/users (the old "Customer accounts" page) and links send ?view=accounts.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("view") === "accounts") setView("accounts");
  }, []);
  const tabs: { id: View; label: string }[] = [
    { id: "buyers", label: "All customers" },
    { id: "accounts", label: "Logins and passwords" },
  ];
  const showAccounts = canAccounts && view === "accounts";
  return (
    <div>
      <PageHeader
        title="Customers"
        description={
          showAccounts
            ? "Every shopper account. Edit a name or email, set a new password, or switch an account off."
            : "Everyone who bought or signed up, one row per person: guests, account holders and accounts that are switched off."
        }
      />
      {canAccounts && <Tabs tabs={tabs} value={view} onChange={setView} label="Customer view" className="mb-6" />}
      {showAccounts ? (
        <AccountsAdmin key={accountQuery} scope="customers" embedded initialQuery={accountQuery} />
      ) : (
        <Buyers
          onManageLogin={
            canAccounts
              ? (email) => {
                  setAccountQuery(email);
                  setView("accounts");
                }
              : undefined
          }
        />
      )}
    </div>
  );
}

function Buyers({ onManageLogin }: { onManageLogin?: (email: string) => void }) {
  const { can } = useAuth();
  const { push } = useToast();
  const canAccounts = can("users:manage");
  const [account, setAccount] = useState("all");
  const [switching, setSwitching] = useState<{ id: number; active: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [segment, setSegment] = useState("");
  const [sort, setSort] = useState("revenue");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CustomerList | null>(null);
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [error, setError] = useState("");

  // Links from the reports open a search (?q=email) or a segment (?segment=vip).
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const found = p.get("q");
    if (found) {
      setQ(found);
      setDraft(found);
    }
    if (p.get("segment")) setSegment(p.get("segment") ?? "");
  }, []);

  const query = useCallback(() => {
    const p = new URLSearchParams({ sort, page: String(page), page_size: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    if (segment) p.set("segment", segment);
    if (account !== "all") p.set("account", account);
    return p;
  }, [q, sort, page, segment, account]);

  const load = useCallback(() => {
    apiFetch<CustomerList>(`/admin/customers?${query()}`).then(
      (d) => {
        setData(d);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [query]);
  useEffect(load, [load]);

  const openDetail = (email: string) =>
    apiFetch<CustomerDetail>(`/admin/customers/detail?email=${encodeURIComponent(email)}`).then(setDetail, (e) => setError(e.message));

  async function switchAccount() {
    if (!switching || !detail) return;
    setBusy(true);
    try {
      await apiFetch(`/users/${switching.id}`, { method: "PATCH", body: JSON.stringify({ is_active: switching.active }) });
      push({ title: switching.active ? "Account switched on" : "Account switched off", description: detail.summary.email });
      setSwitching(null);
      await openDetail(detail.summary.email);
      load();
    } catch (e) {
      push({ title: "Not changed", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  const label = (key: string) => data?.segments.find((s) => s.key === key)?.label ?? key;

  const columns: Column<Customer>[] = [
    {
      key: "who",
      header: "Customer",
      cell: (c) => (
        <div className="min-w-0">
          <button
            type="button"
            className="block max-w-[18rem] truncate text-left font-medium hover:underline"
            onClick={() => void openDetail(c.email)}
          >
            {c.name || c.email}
          </button>
          <span className="block max-w-[18rem] truncate text-xs text-muted">
            {c.name ? c.email : ""}
            {c.subscribed ? `${c.name ? " · " : ""}subscribed` : ""}
          </span>
        </div>
      ),
    },
    { key: "segment", header: "Group", cell: (c) => <Pill tone={SEGMENT_TONE[c.segment] ?? "neutral"}>{label(c.segment)}</Pill> },
    { key: "account", header: "Account", hide: "sm", cell: (c) => <AccountPill c={c} /> },
    { key: "orders", header: "Orders", align: "right", cell: (c) => <span className="num">{c.orders}</span> },
    { key: "revenue", header: "Spent", align: "right", cell: (c) => <span className="num">{money(c.revenue)}</span> },
    { key: "aov", header: "Average order", align: "right", hide: "md", cell: (c) => <span className="num">{money(c.average_order)}</span> },
    { key: "last", header: "Last order", hide: "lg", cell: (c) => <span className="text-sm text-muted">{c.last_order_at ? timeAgo(c.last_order_at) : "—"}</span> },
  ];

  return (
    <div>
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}

      <ul className="mb-6 grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Customer groups">
        {(data?.segments ?? []).map((s) => (
          <li key={s.key}>
            <button
              type="button"
              aria-pressed={segment === s.key}
              onClick={() => {
                setSegment(segment === s.key ? "" : s.key);
                setPage(1);
              }}
              className={`h-full w-full rounded-[var(--radius-card)] border bg-surface p-4 text-left hover:border-ink/30 ${segment === s.key ? "border-accent ring-1 ring-accent" : "border-line"}`}
            >
              <span className="flex items-center justify-between gap-2">
                <Pill tone={SEGMENT_TONE[s.key] ?? "neutral"}>{s.label}</Pill>
                <span className="num text-lg font-medium">{s.customers}</span>
              </span>
              <span className="mt-2 block text-xs text-muted">{s.help}</span>
              <span className="num mt-1 block text-sm">{money(s.revenue)} spent</span>
            </button>
          </li>
        ))}
      </ul>
      {data && (
        <p className="mb-4 text-sm text-muted">
          {data.total_customers} people have bought, and {data.accounts_without_orders} more signed up without ordering yet.{" "}
          {data.subscribers_without_orders} newsletter subscribers haven&apos;t bought yet; reach them with an email campaign.
        </p>
      )}

      <Panel>
        <form
          className="flex flex-wrap items-center gap-3 px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(draft.trim());
            setPage(1);
          }}
        >
          <label htmlFor="customer-search" className="sr-only">
            Search customers
          </label>
          <Input id="customer-search" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Name or email" className="h-9 max-w-xs" />
          <Button type="submit" size="sm" variant="secondary">
            Search
          </Button>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">Show</span>
            <select
              className="h-9 rounded-lg border border-line bg-surface px-2"
              value={account}
              onChange={(e) => {
                setAccount(e.target.value);
                setPage(1);
              }}
            >
              {ACCOUNT_FILTERS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
          {segment && (
            <Button size="sm" variant="ghost" onClick={() => setSegment("")}>
              Show all groups
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => downloadFile(`/admin/customers/export.csv?${query()}`, "wcw-customers.csv").catch((e) => setError(e.message))}>
            Export CSV
          </Button>
          <label className="ml-auto flex items-center gap-2 text-sm">
            <span className="text-muted">Sort</span>
            <select className="h-9 rounded-lg border border-line bg-surface px-2" value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}>
              {SORTS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </form>
        <DataTable columns={columns} rows={data?.items ?? null} rowKey={(c) => c.email} caption="Customers" empty={q || segment || account !== "all" ? "No one matches. Try another search or filter." : "No customers yet. Everyone who orders or signs up appears here."} />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} className="px-4 py-3" />}
      </Panel>

      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail?.summary.name || detail?.summary.email || ""} description={detail?.summary.email} size="lg">
        {detail && (
          <div className="space-y-5 text-sm">
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["Orders", String(detail.summary.orders)],
                ["Spent", money(detail.summary.revenue)],
                ["Average order", money(detail.summary.average_order)],
                ["Refunded", money(detail.refunded)],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-canvas px-3 py-2">
                  <dt className="text-xs text-muted">{k}</dt>
                  <dd className="num font-medium">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="text-muted">
              Group: <span className="text-ink">{label(detail.summary.segment)}</span>
              {detail.summary.first_order_at ? ` · first order ${dateTime(detail.summary.first_order_at)}` : " · no order yet"} ·{" "}
              {detail.reviews} review{detail.reviews === 1 ? "" : "s"} ·{" "}
              {detail.subscription ? (detail.subscription.status === "subscribed" ? "subscribed to news" : "unsubscribed from news") : "not on the email list"}
            </p>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line px-3 py-2">
              <span>
                <span className="font-medium">Account</span>{" "}
                <AccountPill c={detail.summary} />
                <span className="block text-xs text-muted">
                  {detail.summary.account_id
                    ? `Signed up ${detail.summary.joined_at ? dateTime(detail.summary.joined_at) : ""}${detail.summary.account_active ? "" : " · cannot sign in"}`
                    : detail.account_role
                      ? "A team account: manage it on the Team page."
                      : "Bought as a guest, without an account."}
                </span>
              </span>
              {detail.summary.account_id && canAccounts && (
                <span className="flex flex-wrap gap-2">
                  {onManageLogin && (
                    <Button size="sm" variant="ghost" onClick={() => { const e = detail.summary.email; setDetail(null); onManageLogin(e); }}>
                      Edit login
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setSwitching({ id: detail.summary.account_id as number, active: !detail.summary.account_active })}
                  >
                    {detail.summary.account_active ? "Switch account off" : "Switch account on"}
                  </Button>
                </span>
              )}
            </div>
            {detail.orders.length > 0 && <div>
              <h3 className="mb-2 font-medium">Orders</h3>
              <ul className="divide-y divide-line rounded-lg border border-line">
                {detail.orders.map((o) => {
                  const s = ORDER_STATUS[o.status] ?? { label: o.status, tone: "neutral" as const };
                  return (
                    <li key={o.id} className="flex items-center justify-between gap-3 px-3 py-2">
                      <span>
                        <Link href={`/admin/orders/${o.id}`} className="num font-medium text-accent underline underline-offset-4">
                          {o.number}
                        </Link>
                        <span className="block text-xs text-muted">
                          {o.placed_at ? dateTime(o.placed_at) : ""}
                          {o.coupon_code ? ` · ${o.coupon_code}` : ""}
                        </span>
                      </span>
                      <span className="flex items-center gap-3">
                        <Pill tone={s.tone}>{s.label}</Pill>
                        <span className="num">{money(o.grand_total)}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>}
            {detail.coupons.length > 0 && (
              <div>
                <h3 className="mb-2 font-medium">Their personal codes</h3>
                <ul className="space-y-1">
                  {detail.coupons.map((c) => (
                    <li key={c.code}>
                      <span className="font-mono">{c.code}</span> · {c.kind === "percent" ? `${c.value}% off` : c.kind === "fixed" ? `${money(c.value)} off` : "free shipping"} · {c.status}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Modal>
      <ConfirmDialog
        open={!!switching}
        title={switching?.active ? "Switch this account on?" : "Switch this account off?"}
        tone={switching?.active ? "primary" : "danger"}
        typeToConfirm={false}
        confirmLabel={switching?.active ? "Switch account on" : "Switch account off"}
        busy={busy}
        onCancel={() => setSwitching(null)}
        onConfirm={() => void switchAccount()}
        message={
          <p>
            {switching?.active
              ? `${detail?.summary.email} can sign in again.`
              : `${detail?.summary.email} can't sign in until you switch the account back on. If they try, they're told the account is disabled and you get an email. Their orders are kept.`}
          </p>
        }
      />
    </div>
  );
}

function AccountPill({ c }: { c: Customer }) {
  if (c.account_id == null) return <Pill tone="neutral">{c.has_account ? "Team" : "Guest"}</Pill>;
  return c.account_active ? <Pill tone="success">Account</Pill> : <Pill tone="danger">Switched off</Pill>;
}
