"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { intlLocale } from "@/i18n/config";
import { useI18n } from "@/i18n/client";
import { countryName } from "@/lib/account";
import { useCart } from "@/lib/cart";
import { ApiRequestError, apiFetch } from "@/lib/client-api";
import type { Order, OrderAddress } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { Alert, Badge, Container } from "@/components/ui/misc";
import { STATUS_TONE, trackingUrl } from "./status";

const POLL_MS = 3000;
const POLL_LIMIT = 40; // about two minutes of waiting for the payment confirmation

export function AddressBlock({ address }: { address: OrderAddress }) {
  const { locale } = useI18n();
  return (
    <address className="not-italic leading-relaxed text-muted">
      {address.full_name}
      <br />
      {address.company && (
        <>
          {address.company}
          <br />
        </>
      )}
      {address.line1}
      {address.line2 && <>, {address.line2}</>}
      <br />
      {address.city}
      {address.region && <>, {address.region}</>} {address.postal_code}
      <br />
      {countryName(address.country, locale)}
    </address>
  );
}

/**
 * One order, for the customer: opened with the secret link from the confirmation email, or while signed in.
 * Right after paying on Stripe the payment can take a moment to be confirmed, so the page keeps checking.
 */
export function OrderView({ number }: { number: string }) {
  const { t, href, fmt, locale } = useI18n();
  const { clear } = useCart();
  const [order, setOrder] = useState<Order | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const [fresh, setFresh] = useState(false);
  const [returned, setReturned] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const paid = params.get("paid") === "1";
    setFresh(paid || params.get("new") === "1");
    setReturned(paid);
    if (paid) clear(); // back from the payment page: the cart has been turned into this order

    let live = true;
    let tries = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function load() {
      try {
        const path = `/orders/${encodeURIComponent(number)}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
        const next = await apiFetch<Order>(path);
        if (!live) return;
        setOrder(next);
        setState("ready");
        const waiting = paid && next.status === "pending" && next.payment_provider === "stripe";
        if (waiting && ++tries < POLL_LIMIT) timer = setTimeout(load, POLL_MS);
      } catch (err) {
        if (!live) return;
        setState(err instanceof ApiRequestError && err.status === 404 ? "missing" : "error");
      }
    }
    void load();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
    // The cart is cleared once, when the page opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [number]);

  if (state === "loading") {
    return <Container className="py-16 text-muted">{t.order.loading}</Container>;
  }
  if (state === "missing" || state === "error" || !order) {
    return (
      <Container className="max-w-xl py-16 sm:py-24">
        <h1 className="text-4xl">{state === "error" ? t.account.ordersError : t.order.notFoundTitle}</h1>
        <p className="mt-4 text-muted">{state === "error" ? t.checkout.error : t.order.notFoundText}</p>
        <p className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <Link href={href("/login")} className="text-accent underline underline-offset-2">
            {t.checkout.signIn}
          </Link>
          <Link href={href("/contact")} className="text-accent underline underline-offset-2">
            {t.order.contact}
          </Link>
        </p>
      </Container>
    );
  }

  const money = (n: number) => formatPrice(n, order.currency, locale);
  const when = (iso: string | null) =>
    iso ? new Intl.DateTimeFormat(intlLocale[locale], { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso)) : "";
  const confirming = returned && order.status === "pending" && order.payment_provider === "stripe";
  const track = trackingUrl(order.carrier, order.tracking_number);
  const hasDiscount = order.discount_total > 0;

  return (
    <Container className="max-w-4xl py-12 sm:py-16">
      {fresh && order.status !== "cancelled" && (
        <div className="mb-8 rounded-[var(--radius-card)] border border-accent/30 bg-accent-soft px-6 py-5">
          <p className="font-serif text-2xl font-light text-accent-strong">{t.order.thanks}</p>
          <p className="mt-1 text-sm text-accent-strong">{fmt(t.order.thanksText, { email: order.email })}</p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h1 className="text-4xl sm:text-5xl">{fmt(t.order.title, { number: order.number })}</h1>
        <Badge tone={STATUS_TONE[order.status]}>{t.order.status[order.status] ?? order.status}</Badge>
      </div>
      {order.placed_at && <p className="mt-2 text-sm text-muted">{fmt(t.order.placed, { date: when(order.placed_at) })}</p>}

      {confirming && (
        <Alert tone="info" className="mt-6">
          {t.order.confirming}
        </Alert>
      )}
      {order.status === "pending" && order.payment_instructions && (
        <section aria-labelledby="how-to-pay" className="mt-6 rounded-[var(--radius-card)] border border-line bg-surface p-5">
          <h2 id="how-to-pay" className="text-xl">
            {t.order.howToPay}
          </h2>
          <p className="mt-2 whitespace-pre-line text-sm">{order.payment_instructions}</p>
        </section>
      )}

      <div className="mt-10 grid gap-10 md:grid-cols-[1fr_18rem]">
        <section aria-labelledby="order-items">
          <h2 id="order-items" className="text-2xl">
            {t.order.items}
          </h2>
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {order.items.map((item) => (
              <li key={item.id} className="flex items-start justify-between gap-4 py-4 text-sm">
                <div className="min-w-0">
                  <p className="font-medium leading-snug">{item.title}</p>
                  <p className="text-muted">{fmt(t.checkout.qty, { count: item.quantity })}</p>
                </div>
                <p className="font-medium tabular-nums">{money(item.line_total)}</p>
              </li>
            ))}
          </ul>

          <h2 className="mt-8 text-2xl">{t.order.summary}</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt>{t.cart.subtotal}</dt>
              <dd className="tabular-nums">{money(order.subtotal)}</dd>
            </div>
            {hasDiscount && (
              <div className="flex justify-between gap-4 text-success">
                <dt>
                  {t.cart.discount}
                  {order.coupon_code && <span className="whitespace-nowrap"> ({order.coupon_code})</span>}
                </dt>
                <dd className="tabular-nums">−{money(order.discount_total)}</dd>
              </div>
            )}
            <div className="flex justify-between gap-4">
              <dt>{t.cart.shipping}</dt>
              <dd className="tabular-nums">{order.shipping_total > 0 ? money(order.shipping_total) : t.cart.free}</dd>
            </div>
            {order.tax_lines.map((tax) => (
              <div key={tax.name} className="flex justify-between gap-4 text-muted">
                <dt>{tax.name}</dt>
                <dd className="tabular-nums">{money(Number(tax.amount))}</dd>
              </div>
            ))}
            <div className="flex justify-between gap-4 border-t border-line pt-3 text-base">
              <dt className="font-medium">{t.cart.total}</dt>
              <dd className="font-medium tabular-nums">{money(order.grand_total)}</dd>
            </div>
            {order.refunded_total > 0 && (
              <div className="flex justify-between gap-4 text-muted">
                <dt>{t.order.refundedTotal}</dt>
                <dd className="tabular-nums">−{money(order.refunded_total)}</dd>
              </div>
            )}
          </dl>
          {order.notes && (
            <p className="mt-6 text-sm text-muted">
              <span className="font-medium text-ink">{t.order.note}:</span> {order.notes}
            </p>
          )}
        </section>

        <div className="space-y-8 text-sm">
          {order.shipping_address && (
            <section aria-labelledby="order-ship-to">
              <h2 id="order-ship-to" className="text-xl">
                {t.order.shipTo}
              </h2>
              <div className="mt-2">
                <AddressBlock address={order.shipping_address} />
              </div>
            </section>
          )}
          {order.shipping_method && (
            <section aria-labelledby="order-delivery">
              <h2 id="order-delivery" className="text-xl">
                {t.order.delivery}
              </h2>
              <p className="mt-2 text-muted">{order.shipping_method}</p>
              {order.tracking_number && (
                <p className="mt-2 text-muted">
                  {order.carrier && <>{t.order.carrier}: {order.carrier}<br /></>}
                  {t.order.tracking}: <span className="font-medium text-ink">{order.tracking_number}</span>
                </p>
              )}
              {track && (
                <a href={track} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-accent underline underline-offset-2">
                  {t.order.trackPackage}
                  <span className="sr-only"> {t.footer.newTab}</span>
                </a>
              )}
            </section>
          )}
          {order.events.length > 0 && (
            <section aria-labelledby="order-history">
              <h2 id="order-history" className="text-xl">
                {t.order.history}
              </h2>
              <ol className="mt-3 space-y-3 border-l border-line pl-4">
                {order.events.map((event) => (
                  <li key={event.id}>
                    <p className="font-medium">{t.order.events[event.kind] ?? event.message}</p>
                    <p className="text-xs text-muted">{when(event.created_at)}</p>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      </div>

      <p className="mt-12 text-sm text-muted">
        {t.order.help}{" "}
        <Link href={href("/contact")} className="text-accent underline underline-offset-2">
          {t.order.contact}
        </Link>
      </p>
    </Container>
  );
}
