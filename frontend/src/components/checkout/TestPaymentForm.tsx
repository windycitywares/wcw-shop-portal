"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { ApiRequestError } from "@/lib/client-api";
import { ordersApi } from "@/lib/orders";
import type { PublicOrder } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

/** "MM/YY" or "MM/YYYY" → month and four-digit year, or null. */
export function parseExpiry(value: string): { month: number; year: number } | null {
  const m = /^\s*(\d{1,2})\s*\/\s*(\d{2}|\d{4})\s*$/.exec(value);
  if (!m) return null;
  const month = Number(m[1]);
  if (month < 1 || month > 12) return null;
  return { month, year: m[2].length === 2 ? 2000 + Number(m[2]) : Number(m[2]) };
}

export function TestPaymentForm({ token }: { token: string }) {
  const { t, locale, href } = useI18n();
  const [order, setOrder] = useState<PublicOrder | null>(null);
  const [number, setNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [expiryError, setExpiryError] = useState("");

  useEffect(() => {
    ordersApi.byToken(token, locale).then(setOrder, () => undefined);
  }, [token, locale]);

  const orderPath = href(`/order/${token}`);

  async function pay(e: React.FormEvent) {
    e.preventDefault();
    const parsed = parseExpiry(expiry);
    setExpiryError(parsed ? "" : t.testPayment.invalidExpiry);
    if (!parsed) return;
    setBusy(true);
    setError("");
    try {
      const r = await ordersApi.payTestCard(token, { number, exp_month: parsed.month, exp_year: parsed.year, cvc });
      if (r.status === "paid") {
        window.location.assign(`${orderPath}?paid=1`);
        return;
      }
      setError(r.message ?? t.testPayment.error);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : t.testPayment.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={pay} className="space-y-5 rounded-[var(--radius-card)] border border-line bg-surface p-6" noValidate>
      <h1 className="text-3xl">{t.testPayment.title}</h1>
      <Alert tone="info">{t.testPayment.notice}</Alert>
      {order && (
        <p className="flex justify-between text-sm">
          <span className="text-muted">
            {t.testPayment.total} · {order.number}
          </span>
          <span className="font-medium tabular-nums">{formatPrice(order.grand_total, order.currency, locale)}</span>
        </p>
      )}
      {error && (
        <Alert tone="danger">
          <strong>{t.testPayment.declined}.</strong> {error}
        </Alert>
      )}
      <Field label={t.testPayment.cardNumber}>
        {(p) => <Input {...p} inputMode="numeric" autoComplete="off" placeholder="4242 4242 4242 4242" maxLength={23} value={number} onChange={(e) => setNumber(e.target.value)} required />}
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label={t.testPayment.expiry} error={expiryError}>
          {(p) => <Input {...p} inputMode="numeric" autoComplete="off" placeholder="12/30" maxLength={7} value={expiry} onChange={(e) => setExpiry(e.target.value)} required />}
        </Field>
        <Field label={t.testPayment.cvc}>
          {(p) => <Input {...p} inputMode="numeric" autoComplete="off" placeholder="123" maxLength={4} value={cvc} onChange={(e) => setCvc(e.target.value)} required />}
        </Field>
      </div>
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? t.testPayment.paying : order ? `${t.testPayment.pay} ${formatPrice(order.grand_total, order.currency, locale)}` : t.testPayment.pay}
      </Button>
      <p className="text-center text-sm">
        <ButtonLink href={`${orderPath}?payment=cancelled`} variant="ghost">
          {t.testPayment.cancel}
        </ButtonLink>
      </p>
    </form>
  );
}
