"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiRequestError, apiFetch } from "@/lib/client-api";
import type { Order } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { trackingUrl } from "@/components/orders/status";
import { AdminAddress } from "@/components/admin/orders/AdminAddress";
import { CARRIERS, PROVIDER_LABEL, STATUS_LABEL, STATUS_TONE, fmtDateTime } from "@/components/admin/orders/format";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

type Dialog = null | "paid" | "ship" | "cancel" | "refund";

export default function AdminOrder() {
  const { number } = useParams<{ number: string }>();
  const { push } = useToast();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");
  const [missing, setMissing] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try {
      const o = await apiFetch<Order>(`/orders/${encodeURIComponent(number)}`);
      setOrder(o);
      setNote(o.internal_note ?? "");
      setError("");
    } catch (e) {
      if (e instanceof ApiRequestError && e.status === 404) setMissing(true);
      else setError(e instanceof Error ? e.message : "Failed to load the order");
    }
  }, [number]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Runs one action on the order. Returns true when it worked (so a dialog can close). */
  async function act(path: string, method: "POST" | "PUT", body: unknown, done: string): Promise<boolean> {
    setBusy(true);
    setFormError("");
    try {
      const updated = await apiFetch<Order>(`/orders/${encodeURIComponent(number)}/${path}`, { method, body: JSON.stringify(body) });
      setOrder(updated);
      setNote(updated.internal_note ?? "");
      push({ title: done, description: updated.number });
      return true;
    } catch (e) {
      const text = e instanceof Error ? e.message : "That didn't work";
      if (dialog) setFormError(text);
      else setError(text);
      return false;
    } finally {
      setBusy(false);
    }
  }

  if (missing) {
    return (
      <div>
        <PageHeader title="Order not found" back={{ href: "/admin/orders", label: "Orders" }} description="Check the number, or go back to the list." />
      </div>
    );
  }
  if (!order) {
    return (
      <div>
        <PageHeader title={`Order ${number}`} back={{ href: "/admin/orders", label: "Orders" }} />
        {error ? <Alert tone="danger">{error}</Alert> : <div className="skeleton h-64 w-full" aria-label="Loading order" />}
      </div>
    );
  }

  const money = (n: number) => formatPrice(n, order.currency);
  const remaining = Math.max(0, Math.round((order.grand_total - order.refunded_total) * 100) / 100);
  const paid = order.paid_at != null;
  const track = trackingUrl(order.carrier, order.tracking_number);
  const attention = order.events.filter((e) => e.kind === "payment_after_cancel" || e.kind === "payment_mismatch");
  const open = (d: Dialog) => {
    setFormError("");
    setDialog(d);
  };
  const close = () => setDialog(null);

  const actions = (
    <>
      {order.status === "pending" && (
        <Button size="sm" className="h-9" onClick={() => open("paid")}>
          Mark as paid
        </Button>
      )}
      {order.status === "paid" && (
        <Button size="sm" variant="secondary" className="h-9" onClick={async () => void (await act("status", "POST", { status: "processing" }, "Marked as being prepared"))}>
          Start preparing
        </Button>
      )}
      {(order.status === "paid" || order.status === "processing") && (
        <Button size="sm" className="h-9" onClick={() => open("ship")}>
          Ship order
        </Button>
      )}
      {order.status === "shipped" && (
        <Button size="sm" className="h-9" onClick={async () => void (await act("status", "POST", { status: "delivered" }, "Marked as delivered"))}>
          Mark as delivered
        </Button>
      )}
      {paid && remaining > 0 && (
        <Button size="sm" variant="secondary" className="h-9" onClick={() => open("refund")}>
          Refund
        </Button>
      )}
      {["pending", "paid", "processing"].includes(order.status) && (
        <Button size="sm" variant="secondary" className="h-9 text-danger" onClick={() => open("cancel")}>
          Cancel order
        </Button>
      )}
    </>
  );

  return (
    <div>
      <PageHeader
        title={`Order ${order.number}`}
        back={{ href: "/admin/orders", label: "Orders" }}
        description={
          <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
            <Pill tone={STATUS_TONE[order.status]}>{STATUS_LABEL[order.status]}</Pill>
            <span>Placed {fmtDateTime(order.placed_at)}</span>
          </span>
        }
        actions={actions}
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      {attention.map((e) => (
        <Alert key={e.id} tone="danger" className="mb-4">
          {e.message}
        </Alert>
      ))}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <Panel>
            <PanelHeader title="Items" />
            <ul className="divide-y divide-line">
              {order.items.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-4 px-5 py-3 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium">{item.title}</p>
                    <p className="text-xs text-muted">
                      <span className="font-mono">{item.sku}</span> · {money(item.unit_price)} × {item.quantity}
                      {item.list_price != null && item.list_price > item.unit_price && (
                        <span className="ml-1">
                          (was <s>{money(item.list_price)}</s>)
                        </span>
                      )}
                    </p>
                  </div>
                  <p className="num font-medium">{money(item.line_total)}</p>
                </li>
              ))}
            </ul>
            <dl className="space-y-1.5 border-t border-line px-5 py-4 text-sm">
              <Row label="Subtotal" value={money(order.subtotal)} />
              {order.sale_savings > 0 && <Row label="Already reduced by sales" value={`−${money(order.sale_savings)}`} muted />}
              {order.discount_total > 0 && <Row label={`Discount${order.coupon_code ? ` (${order.coupon_code})` : ""}`} value={`−${money(order.discount_total)}`} />}
              <Row label={`Shipping${order.shipping_method ? ` · ${order.shipping_method}` : ""}`} value={order.shipping_total > 0 ? money(order.shipping_total) : "Free"} />
              {order.tax_lines.map((t) => (
                <Row key={t.name} label={t.name} value={money(Number(t.amount))} muted />
              ))}
              <div className="flex justify-between gap-4 border-t border-line pt-2 text-base font-semibold">
                <dt>Total</dt>
                <dd className="num">{money(order.grand_total)}</dd>
              </div>
              {order.refunded_total > 0 && <Row label="Refunded" value={`−${money(order.refunded_total)}`} />}
            </dl>
          </Panel>

          <Panel>
            <PanelHeader title="History" description="Everything that has happened to this order." />
            <ol className="space-y-4 px-5 py-4 text-sm">
              {order.events.map((e) => (
                <li key={e.id} className="flex gap-3">
                  <span aria-hidden="true" className="mt-1.5 size-2 shrink-0 rounded-full bg-accent" />
                  <div>
                    <p>{e.message}</p>
                    <p className="text-xs text-muted">{fmtDateTime(e.created_at)}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel>
            <PanelHeader title="Customer" />
            <PanelBody className="space-y-3 text-sm">
              <p>
                <a href={`mailto:${order.email}`} className="text-accent hover:underline">
                  {order.email}
                </a>
              </p>
              {order.user_id != null && (
                <p className="text-muted">
                  Has an account ·{" "}
                  <Link href={`/admin/users`} className="underline">
                    Team and customers
                  </Link>
                </p>
              )}
              {order.shipping_address && <AdminAddress address={order.shipping_address} />}
              {order.notes && (
                <div>
                  <p className="text-xs font-medium text-muted">Note from the customer</p>
                  <p className="whitespace-pre-line">{order.notes}</p>
                </div>
              )}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Payment" />
            <PanelBody className="space-y-1.5 text-sm">
              <p>{order.payment_provider ? PROVIDER_LABEL[order.payment_provider] : "—"}</p>
              <p className="text-muted">{paid ? `Paid ${fmtDateTime(order.paid_at)}` : order.status === "cancelled" ? "Never paid" : "Not paid yet"}</p>
              {order.payment_ref && <p className="break-all font-mono text-xs text-muted">{order.payment_ref}</p>}
              {order.status === "pending" && order.payment_provider === "offline" && (
                <p className="text-muted">The customer was shown how to pay by invoice. Mark the order as paid when the money arrives.</p>
              )}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Delivery" />
            <PanelBody className="space-y-1.5 text-sm">
              <p>{order.shipping_method ?? "—"}</p>
              {order.shipped_at && <p className="text-muted">Shipped {fmtDateTime(order.shipped_at)}</p>}
              {order.delivered_at && <p className="text-muted">Delivered {fmtDateTime(order.delivered_at)}</p>}
              {order.tracking_number && (
                <p className="text-muted">
                  {order.carrier ?? "Tracking"}: <span className="font-medium text-ink">{order.tracking_number}</span>
                  {track && (
                    <>
                      {" · "}
                      <a href={track} target="_blank" rel="noopener noreferrer" className="text-accent underline">
                        Track
                        <span className="sr-only"> (opens in a new tab)</span>
                      </a>
                    </>
                  )}
                </p>
              )}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Internal note" description="Only your team sees this." />
            <PanelBody>
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  await act("note", "PUT", { internal_note: note.trim() || null }, "Note saved");
                }}
                className="space-y-3"
              >
                <Field label="Note">{(p) => <Textarea {...p} value={note} onChange={(e) => setNote(e.target.value)} maxLength={4000} className="min-h-24" />}</Field>
                <Button type="submit" size="sm" variant="secondary" disabled={busy || note === (order.internal_note ?? "")}>
                  Save note
                </Button>
              </form>
            </PanelBody>
          </Panel>
        </div>
      </div>

      <ConfirmDialog
        open={dialog === "paid"}
        title="Mark as paid?"
        message="Use this when the money has arrived (for example, an invoice was paid). The customer gets their confirmation email."
        confirmLabel="Mark as paid"
        tone="primary"
        busy={busy}
        onCancel={close}
        onConfirm={async () => {
          if (await act("status", "POST", { status: "paid" }, "Marked as paid")) close();
        }}
      />

      <ShipDialog
        open={dialog === "ship"}
        busy={busy}
        error={formError}
        onClose={close}
        onSubmit={async (data) => {
          if (await act("ship", "POST", data, "Marked as shipped")) close();
        }}
      />

      <CancelDialog
        open={dialog === "cancel"}
        paid={paid}
        busy={busy}
        error={formError}
        onClose={close}
        onSubmit={async (data) => {
          if (await act("cancel", "POST", data, "Order cancelled")) close();
        }}
      />

      <RefundDialog
        open={dialog === "refund"}
        remaining={remaining}
        alreadyRefunded={order.refunded_total > 0}
        currency={order.currency}
        busy={busy}
        error={formError}
        onClose={close}
        onSubmit={async (data) => {
          if (await act("refund", "POST", data, "Refund issued")) close();
        }}
      />
    </div>
  );
}

function Row({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 ${muted ? "text-muted" : ""}`}>
      <dt>{label}</dt>
      <dd className="num">{value}</dd>
    </div>
  );
}

function ShipDialog({
  open,
  busy,
  error,
  onClose,
  onSubmit,
}: {
  open: boolean;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (data: { carrier: string | null; tracking_number: string | null; notify: boolean }) => void;
}) {
  const [carrier, setCarrier] = useState("USPS");
  const [tracking, setTracking] = useState("");
  const [notify, setNotify] = useState(true);
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Ship this order"
      description="Add the tracking number so the customer can follow the package."
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="ship-form" size="sm" className="h-9" disabled={busy}>
            {busy ? "Saving…" : "Mark as shipped"}
          </Button>
        </>
      }
    >
      <form
        id="ship-form"
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ carrier: carrier.trim() || null, tracking_number: tracking.trim() || null, notify });
        }}
      >
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Carrier">
            {(p) => (
              <>
                <Input {...p} list="carrier-options" value={carrier} onChange={(e) => setCarrier(e.target.value)} maxLength={50} />
                <datalist id="carrier-options">
                  {CARRIERS.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              </>
            )}
          </Field>
          <Field label="Tracking number">{(p) => <Input {...p} value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={100} autoComplete="off" />}</Field>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
          Email the customer that it has shipped
        </label>
      </form>
    </Modal>
  );
}

function CancelDialog({
  open,
  paid,
  busy,
  error,
  onClose,
  onSubmit,
}: {
  open: boolean;
  paid: boolean;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (data: { refund: boolean; reason: string | null }) => void;
}) {
  const [refund, setRefund] = useState(true);
  const [reason, setReason] = useState("");
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cancel this order?"
      description="The items go back into stock and any discount code can be used again."
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Keep order
          </Button>
          <Button type="submit" form="cancel-form" variant="danger" size="sm" className="h-9" disabled={busy}>
            {busy ? "Cancelling…" : "Cancel order"}
          </Button>
        </>
      }
    >
      <form
        id="cancel-form"
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ refund: paid && refund, reason: reason.trim() || null });
        }}
      >
        {error && <Alert tone="danger">{error}</Alert>}
        {paid && (
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={refund} onChange={(e) => setRefund(e.target.checked)} className="mt-0.5 size-4 accent-[var(--color-accent)]" />
            <span>
              Refund the payment in full
              <span className="block text-xs text-muted">Card payments go back to the customer&apos;s card automatically. For invoices, send the money back yourself.</span>
            </span>
          </label>
        )}
        <Field label="Reason (optional)" hint="Shown to your team only.">
          {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} />}
        </Field>
      </form>
    </Modal>
  );
}

function RefundDialog({
  open,
  remaining,
  alreadyRefunded,
  currency,
  busy,
  error,
  onClose,
  onSubmit,
}: {
  open: boolean;
  remaining: number;
  alreadyRefunded: boolean;
  currency: string;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (data: { amount: number; reason: string | null; restock: boolean; notify: boolean }) => void;
}) {
  const [amount, setAmount] = useState(String(remaining));
  const [reason, setReason] = useState("");
  const [restock, setRestock] = useState(false);
  const [notify, setNotify] = useState(true);
  // Reset the form each time it opens, to the full remaining amount.
  useEffect(() => {
    if (open) {
      setAmount(remaining.toFixed(2));
      setReason("");
      setRestock(false);
      setNotify(true);
    }
  }, [open, remaining]);
  const value = Number(amount);
  const isFull = !alreadyRefunded && Math.abs(value - remaining) < 0.005;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Refund"
      description={`Up to ${formatPrice(remaining, currency)} can still be refunded.`}
      footer={
        <>
          <Button variant="ghost" size="sm" className="h-9" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="refund-form" size="sm" className="h-9" disabled={busy || !(value > 0)}>
            {busy ? "Refunding…" : "Refund"}
          </Button>
        </>
      }
    >
      <form
        id="refund-form"
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ amount: value, reason: reason.trim() || null, restock: restock && isFull, notify });
        }}
      >
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Amount" hint="Card payments go back to the customer's card automatically.">
          {(p) => <Input {...p} type="number" inputMode="decimal" step="0.01" min="0.01" max={remaining} required value={amount} onChange={(e) => setAmount(e.target.value)} />}
        </Field>
        <Field label="Reason (optional)">{(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} />}</Field>
        <label className={`flex items-start gap-2 text-sm ${isFull ? "" : "opacity-60"}`}>
          <input type="checkbox" checked={restock && isFull} disabled={!isFull} onChange={(e) => setRestock(e.target.checked)} className="mt-0.5 size-4 accent-[var(--color-accent)]" />
          <span>
            Put the items back in stock
            <span className="block text-xs text-muted">Only available when the whole order is refunded in one go.</span>
          </span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
          Email the customer about the refund
        </label>
      </form>
    </Modal>
  );
}
