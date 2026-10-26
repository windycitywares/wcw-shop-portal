"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { CHANNEL_LABEL, ORDER_STATUS } from "@/components/admin/reports";
import { dateTime, money } from "@/components/admin/charts/format";
import { PAYMENT_LABEL, PROVIDER_LABEL, type OrderDetail } from "@/components/admin/orders/types";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { ProductImage } from "@/components/ui/ProductImage";

import { LiveUpdatesBar, changedBy } from "@/components/admin/live/LiveUpdatesBar";
type Dialog = "paid" | "ship" | "refund" | "cancel" | null;
const CARRIERS = ["USPS", "UPS", "FedEx", "DHL", "Other"];

export default function AdminOrderDetail() {
  const { id } = useParams<{ id: string }>();
  const { push } = useToast();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(() => {
    apiFetch<OrderDetail>(`/admin/orders/${id}`)
      .then((o) => {
        setOrder(o);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't load the order"));
  }, [id]);

  useEffect(load, [load]);

  /** Run an order action; the API answers with the updated order. */
  async function act(path: string, body: unknown, done: string) {
    setBusy(true);
    try {
      const updated = await apiFetch<OrderDetail>(`/admin/orders/${id}/${path}`, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
      if (updated && "number" in updated) setOrder(updated);
      else load();
      setDialog(null);
      push({ title: done });
    } catch (e) {
      push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!order) return <div className="skeleton h-64" />;

  const status = ORDER_STATUS[order.status] ?? { label: order.status, tone: "neutral" as const };
  const paid = order.payment_status === "paid" || order.payment_status === "partially_refunded";
  const refundable = Math.max(0, Math.round((order.grand_total - order.refunded_total) * 100) / 100);
  const open = ["pending", "paid", "processing"].includes(order.status);
  const addr = order.shipping_address;

  return (
    <div>
      <PageHeader
        back={{ href: "/admin/orders", label: "Orders" }}
        title={`Order ${order.number}`}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            <Pill tone={status.tone}>{status.label}</Pill>
            <span>{PAYMENT_LABEL[order.payment_status] ?? order.payment_status}</span>
            <span className="text-muted">· {order.placed_at ? dateTime(order.placed_at) : ""}</span>
          </span>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            {order.status === "pending" && order.payment_provider !== "stripe" && (
              <Button size="sm" onClick={() => setDialog("paid")}>
                Mark as paid
              </Button>
            )}
            {order.status === "pending" && order.payment_provider === "stripe" && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => act("check-payment", undefined, "Payment checked with Stripe")}>
                Check payment with Stripe
              </Button>
            )}
            {order.status === "paid" && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => act("status", { status: "processing" }, "Marked as preparing")}>
                Start preparing
              </Button>
            )}
            {(order.status === "paid" || order.status === "processing") && (
              <Button size="sm" onClick={() => setDialog("ship")}>
                Ship order
              </Button>
            )}
            {order.status === "shipped" && (
              <Button size="sm" disabled={busy} onClick={() => act("status", { status: "delivered" }, "Marked as delivered")}>
                Mark delivered
              </Button>
            )}
            {paid && refundable > 0 && (
              <Button size="sm" variant="secondary" onClick={() => setDialog("refund")}>
                Refund
              </Button>
            )}
            {open && (
              <Button size="sm" variant="ghost" onClick={() => setDialog("cancel")}>
                Cancel order
              </Button>
            )}
          </div>
        }
      />
      <LiveUpdatesBar prefixes={["order."]} refId={Number(id)} describe={changedBy("order")} onRefresh={load} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Panel>
            <PanelHeader title="Items" />
            <ul className="divide-y divide-line">
              {order.items.map((item) => (
                <li key={item.id} className="flex items-center gap-4 px-5 py-3">
                  <div className="relative size-12 shrink-0 overflow-hidden rounded bg-sand">
                    <ProductImage src={item.image_url ?? undefined} alt="" sizes="48px" />
                  </div>
                  <div className="min-w-0 flex-1 text-sm">
                    {item.product_id ? (
                      <Link href={`/admin/products/${item.product_id}`} className="font-medium hover:underline">
                        {item.title}
                      </Link>
                    ) : (
                      <span className="font-medium">{item.title}</span>
                    )}
                    <span className="block text-xs text-muted">
                      <span className="font-mono">{item.sku}</span>
                      {Object.entries(item.attributes).map(([k, v]) => ` · ${k}: ${String(v)}`)}
                      {item.refunded_quantity > 0 && ` · ${item.refunded_quantity} refunded`}
                    </span>
                  </div>
                  <div className="num text-right text-sm">
                    {money(item.unit_price)} × {item.quantity}
                    {item.list_price != null && item.list_price > item.unit_price && <s className="ml-1 text-xs text-muted">{money(item.list_price)}</s>}
                    <span className="block font-medium">{money(item.line_total)}</span>
                    {item.unit_cost != null && <span className="block text-xs text-muted">cost {money(item.unit_cost * item.quantity)}</span>}
                  </div>
                </li>
              ))}
            </ul>
            <PanelBody className="border-t border-line">
              <dl className="ml-auto max-w-xs space-y-1.5 text-sm">
                <Row label="Subtotal" value={money(order.subtotal)} />
                {order.discounts.filter((d) => d.amount > 0).map((d) => (
                  <Row key={`${d.type}-${d.label}`} label={d.code ? `${d.label} (${d.code})` : d.label} value={`−${money(d.amount)}`} />
                ))}
                <Row label="Shipping" value={order.shipping_total ? money(order.shipping_total) : "Free"} />
                {order.tax_total > 0 && <Row label={`Tax (${order.tax_rate}%)`} value={money(order.tax_total)} />}
                <Row label="Total" value={money(order.grand_total)} strong />
                {order.refunded_total > 0 && <Row label="Refunded" value={`−${money(order.refunded_total)}`} />}
                {order.profit != null && <Row label="Estimated profit" value={money(order.profit)} muted />}
              </dl>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Timeline" description="Everything that happened to this order. Notes are only visible to staff." />
            <form
              className="flex gap-2 border-b border-line px-5 py-3"
              onSubmit={async (e) => {
                e.preventDefault();
                if (!note.trim()) return;
                await act("note", { message: note.trim() }, "Note added");
                setNote("");
              }}
            >
              <label htmlFor="order-note" className="sr-only">
                Add an internal note
              </label>
              <Input id="order-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add an internal note" maxLength={1000} className="h-9" />
              <Button type="submit" size="sm" variant="secondary" disabled={!note.trim() || busy}>
                Add note
              </Button>
            </form>
            <ol className="divide-y divide-line">
              {order.events.map((e) => (
                <li key={e.id} className="px-5 py-3 text-sm">
                  <p>
                    <span className="font-medium capitalize">{e.type.replace(/_/g, " ")}</span>
                    {e.message && <span className="text-muted"> · {e.message}</span>}
                  </p>
                  <p className="text-xs text-muted">
                    {dateTime(e.created_at)}
                    {e.actor ? ` · ${e.actor}` : ""}
                  </p>
                </li>
              ))}
            </ol>
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel>
            <PanelHeader title="Customer" />
            <PanelBody className="space-y-1 text-sm">
              <p className="font-medium">{order.customer_name ?? "—"}</p>
              <p>
                <a href={`mailto:${order.email}`} className="text-accent underline underline-offset-4">
                  {order.email}
                </a>
              </p>
              {order.phone && <p>{order.phone}</p>}
              <p className="text-muted">
                {order.customer_order_count === 1 ? "First order" : `${order.customer_order_count} orders in total`}
                {order.user_id ? " · has an account" : " · guest"}
                {order.marketing_opt_in ? " · subscribed to news" : ""}
              </p>
              <Button size="sm" variant="ghost" className="-ml-3 mt-2" disabled={busy} onClick={() => act("resend", undefined, "Confirmation email sent")}>
                Resend confirmation email
              </Button>
            </PanelBody>
          </Panel>

          {addr && (
            <Panel>
              <PanelHeader title="Ship to" />
              <PanelBody className="text-sm">
                <address className="not-italic">
                  {[addr.full_name, addr.company, addr.line1, addr.line2, [addr.city, addr.region, addr.postal_code].filter(Boolean).join(", "), addr.country]
                    .filter(Boolean)
                    .map((l) => (
                      <span key={l} className="block">
                        {l}
                      </span>
                    ))}
                </address>
                {order.tracking_number && (
                  <p className="mt-3">
                    {order.carrier} · <span className="font-mono">{order.tracking_number}</span>
                    {order.tracking_url && (
                      <a href={order.tracking_url} target="_blank" rel="noopener noreferrer" className="ml-2 text-accent underline underline-offset-4">
                        Track
                        <span className="sr-only"> (opens in a new tab)</span>
                      </a>
                    )}
                  </p>
                )}
                {order.notes && <p className="mt-3 rounded bg-sand px-3 py-2">Customer note: {order.notes}</p>}
              </PanelBody>
            </Panel>
          )}

          <Panel>
            <PanelHeader title="Payment" />
            <PanelBody className="space-y-2 text-sm">
              <p>
                {PROVIDER_LABEL[order.payment_provider ?? ""] ?? order.payment_provider ?? "—"}
                {order.channel && <span className="text-muted"> · came from {CHANNEL_LABEL[order.channel] ?? order.channel}</span>}
                {order.device && <span className="text-muted"> · {order.device}</span>}
              </p>
              <ul className="space-y-1">
                {order.payments.map((p) => (
                  <li key={p.id} className="flex justify-between gap-3">
                    <span>
                      {p.kind === "refund" ? "Refund" : "Charge"} · {p.status}
                      {p.provider_ref && <span className="block font-mono text-xs text-muted">{p.provider_ref}</span>}
                    </span>
                    <span className="num">{p.kind === "refund" ? "−" : ""}{money(p.amount)}</span>
                  </li>
                ))}
              </ul>
            </PanelBody>
          </Panel>
        </div>
      </div>

      <MarkPaidDialog open={dialog === "paid"} busy={busy} onClose={() => setDialog(null)} onSubmit={(b) => act("mark-paid", b, "Marked as paid")} />
      <ShipDialog open={dialog === "ship"} busy={busy} onClose={() => setDialog(null)} onSubmit={(b) => act("ship", b, "Order shipped")} />
      <RefundDialog open={dialog === "refund"} busy={busy} max={refundable} onClose={() => setDialog(null)} onSubmit={(b) => act("refund", b, "Refund made")} />
      <ConfirmDialog
        open={dialog === "cancel"}
        title={`Cancel order ${order.number}?`}
        message={
          paid
            ? `The customer is refunded ${money(refundable)} in full, the items go back into stock and any coupon can be used again. This can't be undone.`
            : "The items go back into stock and any coupon can be used again. This can't be undone."
        }
        confirmLabel={paid ? "Cancel and refund" : "Cancel order"}
        tone="danger"
        busy={busy}
        onConfirm={() => act("cancel", { refund: true, notify_customer: true }, "Order cancelled")}
        onCancel={() => setDialog(null)}
      />
    </div>
  );
}

function Row({ label, value, strong, muted }: { label: string; value: string; strong?: boolean; muted?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 ${strong ? "border-t border-line pt-1.5 font-medium" : ""} ${muted ? "text-muted" : ""}`}>
      <dt>{label}</dt>
      <dd className="num">{value}</dd>
    </div>
  );
}

function MarkPaidDialog({ open, busy, onClose, onSubmit }: { open: boolean; busy: boolean; onClose: () => void; onSubmit: (b: object) => void }) {
  const [reference, setReference] = useState("");
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Mark as paid"
      description="For money that arrived outside card checkout: bank transfer, check or cash. The customer gets their confirmation email."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={busy} onClick={() => onSubmit({ reference: reference.trim() || null })}>
            Mark as paid
          </Button>
        </>
      }
    >
      <Field label="Reference (optional)" hint="Transfer or check number, for your records.">
        {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={200} />}
      </Field>
    </Modal>
  );
}

function ShipDialog({ open, busy, onClose, onSubmit }: { open: boolean; busy: boolean; onClose: () => void; onSubmit: (b: object) => void }) {
  const [carrier, setCarrier] = useState("USPS");
  const [tracking, setTracking] = useState("");
  const [url, setUrl] = useState("");
  const [notify, setNotify] = useState(true);
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Ship order"
      description="The tracking link is made for you for USPS, UPS, FedEx and DHL."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={busy || (!!url && !/^https?:\/\//.test(url))}
            onClick={() => onSubmit({ carrier, tracking_number: tracking.trim() || null, tracking_url: url.trim() || null, notify_customer: notify })}
          >
            Mark as shipped
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Carrier">
          {(p) => (
            <Select {...p} value={carrier} onChange={(e) => setCarrier(e.target.value)}>
              {CARRIERS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Tracking number">{(p) => <Input {...p} value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={100} />}</Field>
        <Field label="Tracking link (optional)" hint="Only needed for other carriers. Starts with https://">
          {(p) => <Input {...p} type="url" value={url} onChange={(e) => setUrl(e.target.value)} maxLength={500} />}
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
          Email the customer that it's on its way
        </label>
      </div>
    </Modal>
  );
}

function RefundDialog({ open, busy, max, onClose, onSubmit }: { open: boolean; busy: boolean; max: number; onClose: () => void; onSubmit: (b: object) => void }) {
  const [amount, setAmount] = useState(String(max));
  const [reason, setReason] = useState("");
  const [notify, setNotify] = useState(true);
  useEffect(() => setAmount(String(max)), [max, open]);
  const value = Number(amount);
  const valid = value > 0 && value <= max;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Refund"
      description={`Up to ${money(max)} can still be refunded. Card payments are refunded through Stripe; for other methods, return the money yourself and record it here.`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={busy || !valid} onClick={() => onSubmit({ amount: Math.round(value * 100) / 100, reason: reason.trim() || null, notify_customer: notify })}>
            Refund {valid ? money(value) : ""}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Amount" error={amount && !valid ? `Between $0.01 and ${money(max)}` : undefined}>
          {(p) => <Input {...p} type="number" inputMode="decimal" min={0.01} max={max} step={0.01} value={amount} onChange={(e) => setAmount(e.target.value)} />}
        </Field>
        <Field label="Reason (optional)" hint="Shown in the order timeline.">
          {(p) => <Textarea {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} className="min-h-20" />}
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
          Email the customer about the refund
        </label>
      </div>
    </Modal>
  );
}
