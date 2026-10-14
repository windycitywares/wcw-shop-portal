"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { Coupon, Page } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { useCategoryTree } from "@/components/admin/useCategoryOptions";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { COUPON_STATUS_LABEL, COUPON_STATUS_TONE, SOURCE_LABEL, couponUpdateBody, day, describeDiscount, describeRules, randomCode } from "./format";
import { EMPTY_RULES, RulesFields, rulesFromCoupon, rulesPayload, type RulesState } from "./RulesFields";

const PAGE_SIZE = 25;

export function CouponsTab() {
  const { push } = useToast();
  const { options: categories } = useCategoryTree();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Coupon> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Coupon | "new" | null>(null);
  const [deleting, setDeleting] = useState<Coupon | null>(null);
  const [busy, setBusy] = useState(false);

  const categoryName = useCallback((id: number) => categories.find((c) => c.id === id)?.label ?? null, [categories]);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (q) params.set("q", q);
    if (status) params.set("status", status);
    if (source) params.set("source", source);
    setLoading(true);
    try {
      setData(await apiFetch<Page<Coupon>>(`/promotions/coupons?${params}`));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load coupons");
    } finally {
      setLoading(false);
    }
  }, [page, q, status, source]);

  useEffect(() => {
    void load();
  }, [load]);

  async function setActive(c: Coupon, is_active: boolean) {
    try {
      await apiFetch(`/promotions/coupons/${c.id}`, { method: "PUT", body: JSON.stringify(couponUpdateBody(c, { is_active })) });
      push({ title: is_active ? "Code resumed" : "Code paused", description: c.code });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work");
    }
  }

  async function remove(c: Coupon) {
    setBusy(true);
    try {
      await apiFetch(`/promotions/coupons/${c.id}`, { method: "DELETE" });
      push({ title: "Code deleted", description: c.code });
      setDeleting(null);
      await load();
    } catch (e) {
      setDeleting(null);
      setError(e instanceof Error ? e.message : "That didn't work");
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<Coupon>[] = [
    {
      key: "code",
      header: "Code",
      cell: (c) => (
        <div className="min-w-0">
          <p className="font-mono text-sm font-semibold tracking-wide">{c.code}</p>
          <p className="truncate text-xs text-muted">
            {c.issued_to ? `For ${c.issued_to}` : c.campaign ? `Batch ${c.campaign}` : SOURCE_LABEL[c.source]}
            {c.description ? ` · ${c.description}` : ""}
          </p>
        </div>
      ),
    },
    {
      key: "discount",
      header: "Discount",
      cell: (c) => (
        <div>
          <p className="font-medium">{describeDiscount(c.kind, c.value)}</p>
          <p className="text-xs text-muted">{describeRules(c, categoryName).join(" · ") || "No conditions"}</p>
        </div>
      ),
    },
    {
      key: "used",
      header: "Used",
      align: "right",
      hide: "sm",
      cell: (c) => (
        <span className="num">
          {c.used_count}
          {c.usage_limit != null && <span className="text-muted"> / {c.usage_limit}</span>}
          {c.discount_given > 0 && <span className="block text-xs text-muted">{formatPrice(c.discount_given, "USD")} given</span>}
        </span>
      ),
    },
    { key: "status", header: "Status", cell: (c) => <Pill tone={COUPON_STATUS_TONE[c.status]}>{COUPON_STATUS_LABEL[c.status]}</Pill> },
    { key: "ends", header: "Ends", hide: "lg", cell: (c) => <span className="text-muted">{c.expires_at ? day(c.expires_at) : "No end date"}</span> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (c) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" className="h-8" onClick={() => setEditing(c)}>
            Edit<span className="sr-only"> {c.code}</span>
          </Button>
          <Button size="sm" variant="ghost" className="h-8" onClick={() => setActive(c, !c.is_active)}>
            {c.is_active ? "Pause" : "Resume"}
            <span className="sr-only"> {c.code}</span>
          </Button>
          <Button size="sm" variant="ghost" className="h-8 text-danger" onClick={() => setDeleting(c)}>
            Delete<span className="sr-only"> {c.code}</span>
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <form
            role="search"
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              setQ(String(new FormData(e.currentTarget).get("q") || "").trim());
            }}
          >
            <label htmlFor="coupon-q" className="sr-only">
              Search codes
            </label>
            <div className="relative">
              <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <input
                id="coupon-q"
                name="q"
                type="search"
                placeholder="Code or email"
                className="h-8 w-48 rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-2 text-sm placeholder:text-muted/70 focus-visible:border-accent"
              />
            </div>
            <label htmlFor="coupon-status" className="sr-only">
              Status
            </label>
            <Select id="coupon-status" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }} className="h-8 w-36 py-0">
              <option value="">Any status</option>
              {Object.entries(COUPON_STATUS_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
            <label htmlFor="coupon-source" className="sr-only">
              Where it came from
            </label>
            <Select id="coupon-source" value={source} onChange={(e) => { setPage(1); setSource(e.target.value); }} className="h-8 w-40 py-0">
              <option value="">Any source</option>
              {Object.entries(SOURCE_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
            <Button type="submit" variant="secondary" size="sm" className="h-8">
              Search
            </Button>
          </form>
          <Button size="sm" className="h-9" onClick={() => setEditing("new")}>
            <Icon name="plus" className="size-4" />
            New coupon
          </Button>
        </div>
        <DataTable
          caption="Coupons"
          columns={columns}
          rows={data ? data.items : null}
          rowKey={(c) => c.id}
          loading={loading}
          empty={q || status || source ? "No code matches those filters." : "No codes yet. Make one for a mailing, a flyer or a thank-you."}
        />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}
      </Panel>

      <CouponForm
        coupon={editing}
        onClose={() => setEditing(null)}
        onSaved={async (message) => {
          setEditing(null);
          push({ title: message });
          await load();
        }}
      />
      <ConfirmDialog
        open={deleting != null}
        title="Delete this code?"
        message={<>Customers will no longer be able to use <span className="font-mono font-semibold">{deleting?.code}</span>. A code that has been used can only be paused.</>}
        confirmLabel="Delete code"
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && remove(deleting)}
      />
    </div>
  );
}

function CouponForm({ coupon, onClose, onSaved }: { coupon: Coupon | "new" | null; onClose: () => void; onSaved: (message: string) => void | Promise<void> }) {
  const isNew = coupon === "new";
  const [code, setCode] = useState("");
  const [usageLimit, setUsageLimit] = useState("");
  const [active, setActive] = useState(true);
  const [rules, setRules] = useState<RulesState>(EMPTY_RULES);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (coupon == null) return;
    setError("");
    setBusy(false);
    if (coupon === "new") {
      setCode("");
      setUsageLimit("");
      setActive(true);
      setRules(EMPTY_RULES);
      setReady(true);
      return;
    }
    let live = true;
    setReady(false);
    void rulesFromCoupon(coupon).then((r) => {
      if (!live) return;
      setCode(coupon.code);
      setUsageLimit(coupon.usage_limit != null ? String(coupon.usage_limit) : "");
      setActive(coupon.is_active);
      setRules(r);
      setReady(true);
    });
    return () => {
      live = false;
    };
  }, [coupon]);

  const title = useMemo(() => (isNew ? "New coupon" : "Edit coupon"), [isNew]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (coupon == null) return;
    setBusy(true);
    setError("");
    const common = { ...rulesPayload(rules), usage_limit: usageLimit.trim() ? Number(usageLimit) : null, is_active: active };
    try {
      if (coupon === "new") {
        await apiFetch("/promotions/coupons", { method: "POST", body: JSON.stringify({ code: code.trim(), ...common }) });
        await onSaved("Code created");
      } else {
        await apiFetch(`/promotions/coupons/${coupon.id}`, { method: "PUT", body: JSON.stringify(common) });
        await onSaved("Code saved");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the code");
      setBusy(false);
    }
  }

  return (
    <Modal
      open={coupon != null}
      onClose={onClose}
      size="lg"
      title={title}
      description="Customers type the code in their cart or at checkout."
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="coupon-form" size="sm" className="h-9" disabled={busy || !ready}>
            {busy ? "Saving…" : isNew ? "Create code" : "Save changes"}
          </Button>
        </>
      }
    >
      {!ready ? (
        <div className="skeleton h-40 w-full" aria-label="Loading" />
      ) : (
        <form id="coupon-form" onSubmit={submit} className="space-y-5">
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Code" hint={isNew ? "Letters, numbers, dashes. Customers can type it in any case." : "A code can't be renamed once made."}>
              {(p) => (
                <div className="flex gap-2">
                  <Input {...p} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} required minLength={3} maxLength={40} readOnly={!isNew} className="font-mono uppercase" autoComplete="off" />
                  {isNew && (
                    <Button type="button" variant="secondary" size="sm" className="h-auto" onClick={() => setCode(randomCode())}>
                      Make one
                    </Button>
                  )}
                </div>
              )}
            </Field>
            <Field label="Times it can be used in total (optional)" hint="Leave empty for no limit.">
              {(p) => <Input {...p} type="number" inputMode="numeric" step="1" min="1" value={usageLimit} onChange={(e) => setUsageLimit(e.target.value)} />}
            </Field>
          </div>
          <RulesFields value={rules} onChange={setRules} />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
            Code is switched on
          </label>
        </form>
      )}
    </Modal>
  );
}
