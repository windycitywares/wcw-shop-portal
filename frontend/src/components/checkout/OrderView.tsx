"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { countryName } from "@/lib/account";
import { ApiRequestError } from "@/lib/client-api";
import { ordersApi } from "@/lib/orders";
import type { PaymentAction, PublicOrder } from "@/lib/types";
import { cn, formatPrice } from "@/lib/utils";
import { Button, ButtonLink } from "@/components/ui/Button";
import { ProductImage } from "@/components/ui/ProductImage";
import { Alert, EmptyState } from "@/components/ui/misc";

const STEPS = ["placed", "paid", "shipped", "delivered"] as const;

export function OrderView({ token }: { token: string }) {
  const { t, fmt, href, locale } = useI18n();
  const [order, setOrder] = useState<PublicOrder | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing">("loading");
  const [notice, setNotice] = useState<"placed" | "paid" | "cancelled" | null>(null);
  const [payment, setPayment] = useState<PaymentAction | null>(null);
  const [paying, setPaying] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    (async () => {
      try {
        // Back from Stripe: ask the server (which asks Stripe) instead of trusting the address bar.
        const loaded = params.get("paid")
          ? await ordersApi.confirm(token, params.get("session_id"), locale)
          : await ordersApi.byToken(token, locale);
        setOrder(loaded);
        setState("ready");
        if (params.get("payment") === "cancelled") setNotice("cancelled");
        else if (params.get("paid") || params.get("placed")) setNotice(loaded.paid_at ? "paid" : "placed");
        if (params.toString()) window.history.replaceState(null, "", window.location.pathname);
        if (!loaded.paid_at && loaded.status === "pending") {
          setPayment(await ordersApi.pay(token, locale).catch(() => null));
        }
      } catch {
        setState("missing");
      }
    })();
  }, [token, locale]);

  if (state === "loading") return <p className="py-16 text-center text-muted" role="status">{t.order.loading}</p>;
  if (state === "missing" || !order) {
    return (
      <EmptyState title={t.order.notFound}>
        <Link href={href("/contact")} className="underline">
          {t.order.contactUs}
        </Link>
      </EmptyState>
    );
  }

  const money = (n: number) => formatPrice(n, order.currency, locale);
  const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" }) : "");
  const reached: Record<string, string | null> = {
    placed: order.placed_at,
    paid: order.paid_at,
    shipped: order.shipped_at,
    delivered: order.delivered_at,
  };
  const cancelled = order.status === "cancelled";
  const addr = order.shipping_address;

  async function payNow() {
    setPaying(true);
    setProblem(null);
    try {
      const action = await ordersApi.pay(token, locale);
      if (action.status === "redirect" && action.redirect_url) window.location.assign(action.redirect_url);
      else setPayment(action);
    } catch (err) {
      setProblem(err instanceof ApiRequestError ? err.message : t.cart.pricesUnavailable);
    } finally {
      setPaying(false);
    }
  }

  return (
    <div className="space-y-10">
      <div>
        {notice && notice !== "cancelled" && (
          <Alert tone="success" className="mb-6">
            {notice === "paid" ? t.order.paid : t.order.placed}
          </Alert>
        )}
        {notice === "cancelled" && (
          <Alert tone="danger" className="mb-6">
            {t.order.paymentCancelled}
          </Alert>
        )}
        <h1 className="text-4xl sm:text-5xl">{fmt(t.order.title, { number: order.number })}</h1>
        <p className="mt-2 text-muted">
          {order.placed_at && fmt(t.order.placedOn, { date: date(order.placed_at) })} ·{" "}
          <span className="font-medium text-ink">{t.order.status[order.status] ?? order.status}</span>
        </p>
      </div>

      {!cancelled && (
        <ol aria-label={t.order.progress} className="grid grid-cols-4 gap-2 text-xs sm:text-sm">
          {STEPS.map((step) => {
            const done = !!reached[step];
            return (
              <li key={step} className="space-y-2">
                <div className={cn("h-1.5 rounded-full", done ? "bg-success" : "bg-sand")} aria-hidden="true" />
                <p className={done ? "text-ink" : "text-muted"}>
                  {t.order.steps[step]}
                  <span className="sr-only">{done ? ` ✓ ${date(reached[step])}` : ""}</span>
                </p>
                {done && <p aria-hidden="true" className="text-muted">{date(reached[step])}</p>}
              </li>
            );
          })}
        </ol>
      )}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-label={t.order.items} className="space-y-6">
          <ul className="divide-y divide-line border-y border-line">
            {order.items.map((item) => (
              <li key={item.id} className="flex items-center gap-4 py-4">
                <div className="relative size-20 shrink-0 overflow-hidden rounded-md bg-sand">
                  <ProductImage src={item.image_url ?? undefined} alt="" sizes="80px" className="object-contain" />
                </div>
                <div className="min-w-0 flex-1">
                  {item.slug ? (
                    <Link href={href(`/product/${item.slug}`)} className="font-serif text-lg hover:underline">
                      {item.title}
                    </Link>
                  ) : (
                    <p className="font-serif text-lg">{item.title}</p>
                  )}
                  <p className="text-sm text-muted">
                    {money(item.unit_price)} × {item.quantity}
                  </p>
                </div>
                <p className="text-sm font-medium tabular-nums">{money(item.line_total)}</p>
              </li>
            ))}
          </ul>
          <dl className="ml-auto max-w-sm space-y-2 text-sm">
            <div className="flex justify-between">
              <dt>{t.cart.subtotal}</dt>
              <dd>{money(order.subtotal)}</dd>
            </div>
            {order.discounts
              .filter((d) => d.amount > 0)
              .map((d) => (
                <div key={`${d.type}-${d.label}`} className="flex justify-between text-sale">
                  <dt>{d.label}</dt>
                  <dd>−{money(d.amount)}</dd>
                </div>
              ))}
            <div className="flex justify-between">
              <dt>{t.cart.shipping}</dt>
              <dd>{order.shipping_total ? money(order.shipping_total) : t.cart.free}</dd>
            </div>
            {order.tax_total > 0 && (
              <div className="flex justify-between">
                <dt>{t.order.tax}</dt>
                <dd>{money(order.tax_total)}</dd>
              </div>
            )}
            <div className="flex justify-between border-t border-line pt-2 text-base font-medium">
              <dt>{t.cart.total}</dt>
              <dd>{money(order.grand_total)}</dd>
            </div>
            {order.refunded_total > 0 && (
              <div className="flex justify-between text-muted">
                <dt>{t.order.refunded}</dt>
                <dd>−{money(order.refunded_total)}</dd>
              </div>
            )}
          </dl>
        </section>

        <aside className="space-y-6">
          {order.tracking_number || order.tracking_url ? (
            <div className="rounded-[var(--radius-card)] border border-line bg-surface p-5 text-sm">
              {order.carrier && (
                <p>
                  {t.order.carrier}: <span className="font-medium">{order.carrier}</span>
                </p>
              )}
              {order.tracking_number && (
                <p>
                  {t.order.tracking}: <span className="font-medium">{order.tracking_number}</span>
                </p>
              )}
              {order.tracking_url && (
                <ButtonLink href={order.tracking_url} target="_blank" rel="noopener noreferrer" className="mt-3 w-full">
                  {t.order.track}
                </ButtonLink>
              )}
            </div>
          ) : null}

          {payment && payment.status !== "paid" && !cancelled && (
            <div className="rounded-[var(--radius-card)] border border-accent bg-accent-soft p-5 text-sm">
              <h2 className="font-serif text-xl">{t.order.payment}</h2>
              {payment.instructions && (
                <>
                  <p className="mt-2 font-medium">{t.order.howToPay}</p>
                  <p className="mt-1 whitespace-pre-line">{payment.instructions}</p>
                </>
              )}
              {payment.provider === "stripe" && (
                <Button className="mt-3 w-full" onClick={payNow} disabled={paying}>
                  {t.order.payNow}
                </Button>
              )}
              {problem && <p className="mt-2 text-danger">{problem}</p>}
            </div>
          )}

          {addr && (
            <div className="text-sm">
              <h2 className="font-serif text-xl">{t.order.shipTo}</h2>
              <address className="mt-2 not-italic text-muted">
                {[addr.full_name, addr.company, addr.line1, addr.line2, [addr.city, addr.region, addr.postal_code].filter(Boolean).join(", "), countryName(addr.country, locale)]
                  .filter(Boolean)
                  .map((line) => (
                    <span key={line} className="block">
                      {line}
                    </span>
                  ))}
              </address>
            </div>
          )}

          <p className="text-sm text-muted">{t.order.keepLink}</p>
          <p className="text-sm">
            {t.order.questions}{" "}
            <Link href={href("/contact")} className="underline">
              {t.order.contactUs}
            </Link>
          </p>
        </aside>
      </div>
    </div>
  );
}
