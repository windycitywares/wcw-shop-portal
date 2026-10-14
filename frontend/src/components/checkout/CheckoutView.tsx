"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "@/i18n/client";
import { addressesApi, COUNTRIES, countryName, type Address } from "@/lib/account";
import { useAuth } from "@/lib/auth";
import { useCart } from "@/lib/cart";
import { apiFetch } from "@/lib/client-api";
import { useQuote } from "@/lib/quote";
import { useShopConfig } from "@/lib/shop";
import { site } from "@/lib/site";
import type { OrderPlaced, PaymentOption, ShippingOption } from "@/lib/types";
import { cn, formatPrice } from "@/lib/utils";
import { attrKey, attrValue } from "@/i18n/attributes";
import { CouponBox } from "@/components/cart/CouponBox";
import { Totals } from "@/components/cart/Totals";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ProductImage } from "@/components/ui/ProductImage";
import { Alert, Container, EmptyState } from "@/components/ui/misc";
import { Turnstile } from "@/components/ui/Turnstile";

interface AddressDraft {
  full_name: string;
  company: string;
  line1: string;
  line2: string;
  city: string;
  region: string;
  postal_code: string;
  country: string;
  phone: string;
}

const EMPTY: AddressDraft = { full_name: "", company: "", line1: "", line2: "", city: "", region: "", postal_code: "", country: "US", phone: "" };

const fromSaved = (a: Address): AddressDraft => ({
  full_name: a.full_name,
  company: a.company ?? "",
  line1: a.line1,
  line2: a.line2 ?? "",
  city: a.city,
  region: a.region ?? "",
  postal_code: a.postal_code,
  country: a.country,
  phone: a.phone ?? "",
});

/** Only ever send the customer to Stripe's own pages. */
function safePaymentUrl(raw: string | null): string | null {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    const ok = url.protocol === "https:" && (url.hostname === "stripe.com" || url.hostname.endsWith(".stripe.com"));
    return ok ? url.toString() : null;
  } catch {
    return null;
  }
}

export function CheckoutView() {
  const { t, href, fmt, locale } = useI18n();
  const router = useRouter();
  const { user } = useAuth();
  const { lines, coupon, clear } = useCart();
  const config = useShopConfig();

  const [email, setEmail] = useState("");
  const [subscribe, setSubscribe] = useState(false);
  const [addr, setAddr] = useState<AddressDraft>(EMPTY);
  const [saved, setSaved] = useState<Address[]>([]);
  const [savedId, setSavedId] = useState("new");
  const [shippingMethod, setShippingMethod] = useState("");
  const [payment, setPayment] = useState("");
  const [notes, setNotes] = useState("");
  const [captcha, setCaptcha] = useState<string | null>(null);
  const [captchaKey, setCaptchaKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const touched = useRef(false);
  const errorBox = useRef<HTMLDivElement>(null);

  const open = config?.checkout_enabled === true;

  // Sign-in: start from the account's email, name and saved addresses (unless the shopper already typed something).
  useEffect(() => {
    if (!user) return;
    setEmail((current) => current || user.email);
    let live = true;
    addressesApi
      .list()
      .then((list) => {
        if (!live) return;
        setSaved(list);
        if (touched.current) return;
        const pick = list.find((a) => a.is_default) ?? list[0];
        if (pick) {
          setAddr(fromSaved(pick));
          setSavedId(String(pick.id));
        } else if (user.full_name) {
          setAddr((a) => ({ ...a, full_name: a.full_name || user.full_name || "" }));
        }
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [user]);

  const countries = useMemo<string[]>(() => config?.shipping_countries ?? [...COUNTRIES], [config]);
  useEffect(() => {
    if (countries.length > 0 && !countries.includes(addr.country)) setAddr((a) => ({ ...a, country: countries[0] ?? "US" }));
  }, [countries, addr.country]);

  function setField(name: keyof AddressDraft, value: string) {
    touched.current = true;
    setSavedId("new");
    setAddr((a) => ({ ...a, [name]: value }));
  }

  function pickSaved(id: string) {
    touched.current = true;
    setSavedId(id);
    const found = saved.find((a) => String(a.id) === id);
    setAddr(found ? fromSaved(found) : { ...EMPTY, country: addr.country });
  }

  const quoteInput = useMemo(
    () => ({
      lines,
      coupon,
      shippingMethod: shippingMethod || null,
      email: email.trim() || null,
      country: addr.country,
      region: addr.region.trim() || null,
      postalCode: addr.postal_code.trim() || null,
    }),
    [lines, coupon, shippingMethod, email, addr.country, addr.region, addr.postal_code],
  );
  const { quote, quoteCoupon, loading, error: quoteError, refresh } = useQuote(quoteInput, open);

  // Keep the chosen delivery option valid as the address changes: pick the first one on offer when it isn't.
  const options: ShippingOption[] = quote?.shipping_options ?? [];
  const optionCodes = options.map((o) => o.code).join(",");
  useEffect(() => {
    const codes = optionCodes ? optionCodes.split(",") : [];
    if (!quote) return;
    if (codes.length === 0) {
      if (shippingMethod) setShippingMethod("");
    } else if (!codes.includes(shippingMethod)) {
      setShippingMethod(codes[0] ?? "");
    }
  }, [optionCodes, quote, shippingMethod]);

  const paymentOptions: PaymentOption[] = config?.payment_options ?? [];
  useEffect(() => {
    if (paymentOptions.length > 0 && !paymentOptions.some((p) => p.id === payment)) setPayment(paymentOptions[0]?.id ?? "");
  }, [paymentOptions, payment]);

  useEffect(() => {
    if (error) errorBox.current?.focus();
  }, [error]);

  const money = (n: number) => formatPrice(n, quote?.currency ?? "USD", locale);
  const addressReady = addr.line1.trim() !== "" && addr.city.trim() !== "" && addr.postal_code.trim() !== "";
  const needsAttention = quote != null && (quote.unavailable.length > 0 || quote.lines.some((l) => l.issue != null));
  const codeBlocks = quote?.coupon_problem != null && quote.coupon_problem.code !== "needs_email";
  const canPlace =
    open && !!quote && !loading && !busy && !needsAttention && !codeBlocks && !!shippingMethod && !!payment && quote.shipping_method === shippingMethod;

  async function place(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!quote || !canPlace) return;
    setBusy(true);
    setError(null);
    const text = (v: string) => v.trim() || null;
    try {
      const placed = await apiFetch<OrderPlaced>("/checkout", {
        method: "POST",
        body: JSON.stringify({
          items: quoteInput.lines.map((l) => ({ product_id: l.productId, quantity: l.quantity, options: l.options ?? {}, key: l.key })),
          coupon_code: coupon,
          shipping_method: shippingMethod,
          email: email.trim(),
          shipping_address: {
            full_name: addr.full_name.trim(),
            company: text(addr.company),
            line1: addr.line1.trim(),
            line2: text(addr.line2),
            city: addr.city.trim(),
            region: text(addr.region),
            postal_code: addr.postal_code.trim(),
            country: addr.country,
            phone: text(addr.phone),
          },
          notes: text(notes),
          payment_provider: payment,
          expected_total: quote.total,
          locale,
          captcha_token: captcha,
          subscribe,
        }),
      });
      if (placed.next === "pay") {
        const url = safePaymentUrl(placed.payment_url);
        if (!url) throw new Error(t.checkout.error);
        setLeaving(true);
        window.location.assign(url);
        return;
      }
      setLeaving(true);
      clear();
      router.push(`${href(`/order/${placed.number}`)}?token=${encodeURIComponent(placed.access_token)}&new=1`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.checkout.error);
      setCaptchaKey((k) => k + 1); // a CAPTCHA token works once
      refresh();
      setBusy(false);
    }
  }

  const heading = <h1 className="text-5xl sm:text-6xl">{t.checkout.title}</h1>;

  if (leaving) {
    return (
      <Container className="py-12 sm:py-16">
        {heading}
        <p className="mt-8 text-muted" role="status">
          {busy && payment === "stripe" ? t.checkout.redirecting : t.checkout.placing}
        </p>
      </Container>
    );
  }

  if (lines.length === 0) {
    return (
      <Container className="py-12 sm:py-16">
        {heading}
        <div className="mt-10">
          <EmptyState title={t.checkout.emptyTitle}>
            <Link href={href("/shop")} className="underline">
              {t.cart.continue}
            </Link>
          </EmptyState>
        </div>
      </Container>
    );
  }

  if (config === undefined) {
    return (
      <Container className="py-12 sm:py-16">
        {heading}
        <p className="mt-8 text-muted">{t.checkout.loading}</p>
      </Container>
    );
  }

  if (!open) {
    return (
      <Container className="py-12 sm:py-16">
        {heading}
        <div className="mt-10">
          <EmptyState title={config === null ? t.checkout.error : t.checkout.closedTitle}>
            <p className="mx-auto max-w-md">{t.checkout.closedText}</p>
            <p className="mt-4 flex flex-wrap justify-center gap-x-6 gap-y-2">
              <Link href={href("/cart")} className="underline">
                {t.checkout.backToCart}
              </Link>
              <a href={site.social[0].href} target="_blank" rel="noopener noreferrer" className="underline">
                Etsy
                <span className="sr-only"> {t.footer.newTab}</span>
              </a>
              <Link href={href("/contact")} className="underline">
                {t.order.contact}
              </Link>
            </p>
          </EmptyState>
        </div>
      </Container>
    );
  }

  const eta = (o: ShippingOption) => {
    if (o.min_days != null && o.max_days != null && o.min_days !== o.max_days) return fmt(t.checkout.days, { min: o.min_days, max: o.max_days });
    const days = o.max_days ?? o.min_days;
    return days != null ? fmt(t.checkout.day, { count: days }) : null;
  };

  const paymentLabel = (p: PaymentOption) => (p.id === "stripe" ? t.checkout.payCard : p.id === "test" ? t.checkout.payTest : p.label);
  const paymentNote = (p: PaymentOption) => (p.id === "stripe" ? t.checkout.cardNote : p.id === "test" ? t.checkout.testNote : p.description);

  return (
    <Container className="py-12 sm:py-16">
      {heading}
      <div className="mt-10 grid gap-12 lg:grid-cols-[1fr_26rem]">
        <form id="checkout-form" onSubmit={place} className="space-y-10">
          <section aria-labelledby="co-contact" className="space-y-4">
            <h2 id="co-contact" className="text-2xl">
              {t.checkout.contact}
            </h2>
            {!user && (
              <p className="text-sm text-muted">
                {t.checkout.signInHint}{" "}
                <Link href={`${href("/login")}?next=${encodeURIComponent(href("/checkout"))}`} className="text-accent underline underline-offset-2">
                  {t.checkout.signIn}
                </Link>
              </p>
            )}
            <Field label={t.checkout.email} hint={t.checkout.emailHint}>
              {(p) => (
                <Input {...p} name="email" type="email" required maxLength={254} autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              )}
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={subscribe} onChange={(e) => setSubscribe(e.target.checked)} className="h-4 w-4 accent-[var(--color-accent)]" />
              {t.checkout.subscribe}
            </label>
          </section>

          <section aria-labelledby="co-address" className="space-y-4">
            <h2 id="co-address" className="text-2xl">
              {t.checkout.address}
            </h2>
            {saved.length > 0 && (
              <Field label={t.checkout.saved}>
                {(p) => (
                  <Select {...p} value={savedId} onChange={(e) => pickSaved(e.target.value)}>
                    {saved.map((a) => (
                      <option key={a.id} value={String(a.id)}>
                        {[a.label || a.full_name, a.line1, a.city].join(", ")}
                      </option>
                    ))}
                    <option value="new">{t.checkout.useNew}</option>
                  </Select>
                )}
              </Field>
            )}
            <Field label={t.addresses.fullName}>
              {(p) => (
                <Input {...p} name="full_name" required maxLength={200} autoComplete="shipping name" value={addr.full_name} onChange={(e) => setField("full_name", e.target.value)} />
              )}
            </Field>
            <Field label={`${t.addresses.company} ${t.addresses.optional}`}>
              {(p) => (
                <Input {...p} name="company" maxLength={200} autoComplete="shipping organization" value={addr.company} onChange={(e) => setField("company", e.target.value)} />
              )}
            </Field>
            <Field label={t.addresses.line1}>
              {(p) => (
                <Input {...p} name="line1" required maxLength={200} autoComplete="shipping address-line1" value={addr.line1} onChange={(e) => setField("line1", e.target.value)} />
              )}
            </Field>
            <Field label={`${t.addresses.line2} ${t.addresses.optional}`}>
              {(p) => (
                <Input {...p} name="line2" maxLength={200} autoComplete="shipping address-line2" value={addr.line2} onChange={(e) => setField("line2", e.target.value)} />
              )}
            </Field>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label={t.addresses.city}>
                {(p) => (
                  <Input {...p} name="city" required maxLength={100} autoComplete="shipping address-level2" value={addr.city} onChange={(e) => setField("city", e.target.value)} />
                )}
              </Field>
              <Field label={`${t.addresses.region} ${t.addresses.optional}`}>
                {(p) => (
                  <Input {...p} name="region" maxLength={100} autoComplete="shipping address-level1" value={addr.region} onChange={(e) => setField("region", e.target.value)} />
                )}
              </Field>
              <Field label={t.addresses.postalCode}>
                {(p) => (
                  <Input {...p} name="postal_code" required maxLength={20} autoComplete="shipping postal-code" value={addr.postal_code} onChange={(e) => setField("postal_code", e.target.value)} />
                )}
              </Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t.addresses.country}>
                {(p) => (
                  <Select {...p} name="country" autoComplete="shipping country" value={addr.country} onChange={(e) => setField("country", e.target.value)}>
                    {countries.map((c) => (
                      <option key={c} value={c}>
                        {countryName(c, locale)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label={`${t.addresses.phone} ${t.addresses.optional}`} hint={t.addresses.phoneHint}>
                {(p) => (
                  <Input {...p} name="phone" type="tel" maxLength={40} pattern="[0-9+()\-.\s]*" autoComplete="shipping tel" value={addr.phone} onChange={(e) => setField("phone", e.target.value)} />
                )}
              </Field>
            </div>
          </section>

          <fieldset className="space-y-3">
            <legend className="mb-1 text-2xl font-serif">{t.checkout.delivery}</legend>
            {!addressReady ? (
              <p className="text-sm text-muted">{t.checkout.needAddress}</p>
            ) : !quote ? (
              <p className="text-sm text-muted">{t.cart.updating}</p>
            ) : options.length === 0 ? (
              <Alert tone="info">{t.checkout.noDelivery}</Alert>
            ) : (
              options.map((o) => (
                <label
                  key={o.code}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4",
                    "has-[:checked]:border-accent has-[:checked]:bg-accent-soft",
                  )}
                >
                  <input
                    type="radio"
                    name="shipping_method"
                    value={o.code}
                    checked={shippingMethod === o.code}
                    onChange={() => setShippingMethod(o.code)}
                    className="mt-1 h-4 w-4 accent-[var(--color-accent)]"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{o.name}</span>
                    {eta(o) && <span className="block text-sm text-muted">{eta(o)}</span>}
                    {o.description && <span className="block text-sm text-muted">{o.description}</span>}
                  </span>
                  <span className="text-right text-sm font-medium tabular-nums">
                    {o.price > 0 ? money(o.price) : t.cart.free}
                    {o.base_price > o.price && (
                      <s className="ml-2 font-normal text-muted">
                        {money(o.base_price)}
                      </s>
                    )}
                  </span>
                </label>
              ))
            )}
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="mb-1 text-2xl font-serif">{t.checkout.payment}</legend>
            {paymentOptions.length === 0 ? (
              <Alert tone="info">{t.checkout.noPayment}</Alert>
            ) : (
              paymentOptions.map((p) => (
                <label
                  key={p.id}
                  className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4 has-[:checked]:border-accent has-[:checked]:bg-accent-soft"
                >
                  <input
                    type="radio"
                    name="payment_provider"
                    value={p.id}
                    checked={payment === p.id}
                    onChange={() => setPayment(p.id)}
                    className="mt-1 h-4 w-4 accent-[var(--color-accent)]"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{paymentLabel(p)}</span>
                    {paymentNote(p) && <span className="block text-sm text-muted">{paymentNote(p)}</span>}
                  </span>
                </label>
              ))
            )}
          </fieldset>

          <section aria-labelledby="co-notes" className="space-y-3">
            <h2 id="co-notes" className="text-2xl">
              {t.checkout.notes}
            </h2>
            <Field label={t.checkout.notes} hint={t.checkout.notesHint}>
              {(p) => <Textarea {...p} name="notes" maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />}
            </Field>
          </section>
        </form>

        <aside aria-label={t.checkout.summary} className="h-fit space-y-5 rounded-[var(--radius-card)] border border-line bg-surface p-6 lg:sticky lg:top-24">
          <h2 className="text-2xl">{t.checkout.summary}</h2>
          <ul className="divide-y divide-line">
            {lines.map((line) => {
              const priced = quote?.lines.find((l) => l.key === line.key);
              const unit = priced?.unit_price ?? line.price;
              return (
                <li key={line.key} className="flex gap-3 py-3 text-sm">
                  <div className="mat relative size-16 shrink-0 !p-1">
                    <div className="relative size-full overflow-hidden">
                      <ProductImage src={line.image} alt="" sizes="64px" className="object-contain" />
                    </div>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium leading-snug">{line.title}</p>
                    {line.variant && <p className="text-muted">{attrValue(t, line.variant)}</p>}
                    {line.options && Object.keys(line.options).length > 0 && (
                      <p className="text-xs text-muted">
                        {Object.entries(line.options)
                          .map(([k, v]) => `${attrKey(t, k)}: ${attrValue(t, v)}`)
                          .join(", ")}
                      </p>
                    )}
                    <p className="text-muted">{fmt(t.checkout.qty, { count: line.quantity })}</p>
                  </div>
                  <p className="font-medium tabular-nums">{money(unit * line.quantity)}</p>
                </li>
              );
            })}
          </ul>
          <CouponBox quote={quote} quoteCoupon={quoteCoupon} loading={loading} />
          {quote && <Totals quote={quote} showTotal className={loading ? "opacity-60 transition-opacity" : "transition-opacity"} />}
          {quoteError && <Alert tone="danger">{t.cart.priceError}</Alert>}
          {needsAttention && (
            <Alert tone="danger">
              {t.checkout.fixCart}{" "}
              <Link href={href("/cart")} className="underline">
                {t.checkout.backToCart}
              </Link>
            </Alert>
          )}
          {codeBlocks && <Alert tone="danger">{t.checkout.fixCode}</Alert>}
          {quote && addressReady && !shippingMethod && options.length > 0 && <p className="text-sm text-muted">{t.checkout.pickDelivery}</p>}
          <div ref={errorBox} tabIndex={-1} className="outline-none empty:hidden">
            {error && <Alert tone="danger">{error}</Alert>}
          </div>
          <Turnstile action="checkout" onToken={setCaptcha} resetKey={captchaKey} locale={locale} label={t.auth.captcha} />
          <Button type="submit" form="checkout-form" size="lg" className="w-full" disabled={!canPlace}>
            {busy ? t.checkout.placing : payment === "stripe" ? t.checkout.payNow : t.checkout.placeOrder}
          </Button>
          <p className="text-center text-sm">
            <Link href={href("/cart")} className="text-muted underline hover:text-ink">
              {t.checkout.backToCart}
            </Link>
          </p>
        </aside>
      </div>
    </Container>
  );
}
