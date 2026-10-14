"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "@/i18n/client";
import { addressesApi, countryName, type Address } from "@/lib/account";
import { useAuth } from "@/lib/auth";
import { useCart } from "@/lib/cart";
import { ApiRequestError, apiFetch } from "@/lib/client-api";
import { newIdempotencyKey } from "@/lib/orders";
import type { CheckoutResult, Quote, ShopConfig } from "@/lib/types";
import { cn, formatPrice } from "@/lib/utils";
import { CartTotals, CouponForm } from "@/components/cart/CartSummary";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ProductImage } from "@/components/ui/ProductImage";
import { Turnstile } from "@/components/ui/Turnstile";
import { Alert, EmptyState } from "@/components/ui/misc";

type AddressForm = {
  full_name: string;
  company: string;
  line1: string;
  line2: string;
  city: string;
  region: string;
  postal_code: string;
  country: string;
  phone: string;
};

const EMPTY_ADDRESS: AddressForm = {
  full_name: "",
  company: "",
  line1: "",
  line2: "",
  city: "",
  region: "",
  postal_code: "",
  country: "US",
  phone: "",
};
const REQUIRED: (keyof AddressForm)[] = ["full_name", "line1", "city", "postal_code", "country"];
const CART_TOKEN_KEY = "wcw-cart-token";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function fromSaved(a: Address): AddressForm {
  return {
    full_name: a.full_name,
    company: a.company ?? "",
    line1: a.line1,
    line2: a.line2 ?? "",
    city: a.city,
    region: a.region ?? "",
    postal_code: a.postal_code,
    country: a.country,
    phone: a.phone ?? "",
  };
}

function readToken(): string | null {
  try {
    return localStorage.getItem(CART_TOKEN_KEY);
  } catch {
    return null;
  }
}

function saveToken(token: string | null) {
  try {
    if (token) localStorage.setItem(CART_TOKEN_KEY, token);
    else localStorage.removeItem(CART_TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

export function CheckoutForm() {
  const { lines, coupon, clear } = useCart();
  const { user, loading: authLoading } = useAuth();
  const { t, href, locale } = useI18n();
  const router = useRouter();

  const [config, setConfig] = useState<ShopConfig | null>(null);
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState<AddressForm>(EMPTY_ADDRESS);
  const [saved, setSaved] = useState<Address[]>([]);
  const [savedId, setSavedId] = useState<number | "new">("new");
  const [notes, setNotes] = useState("");
  const [method, setMethod] = useState<string>("");
  const [marketing, setMarketing] = useState(false);
  const [reminders, setReminders] = useState(false);
  const [saveAddress, setSaveAddress] = useState(true);
  const [captcha, setCaptcha] = useState<string | null>(null);
  const [captchaKey, setCaptchaKey] = useState(0);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [errors, setErrors] = useState<Partial<Record<keyof AddressForm | "email", string>>>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [stage, setStage] = useState<"form" | "placing" | "redirecting">("form");
  const idempotencyKey = useRef(newIdempotencyKey());

  useEffect(() => {
    apiFetch<ShopConfig>(`/shop/config?lang=${locale}`)
      .then((c) => {
        setConfig(c);
        setMethod((m) => m || c.payment_methods[0] || "");
        setAddress((a) => (c.shipping_countries.includes(a.country) ? a : { ...a, country: c.shipping_countries[0] ?? "US" }));
      })
      .catch(() => setProblem(t.cart.pricesUnavailable));
  }, [locale, t.cart.pricesUnavailable]);

  // Signed in: use the account email and the default saved address.
  useEffect(() => {
    if (!user) return;
    setEmail((e) => e || user.email);
    addressesApi
      .list()
      .then((list) => {
        setSaved(list);
        const preferred = list.find((a) => a.is_default) ?? list[0];
        if (preferred) {
          setSavedId(preferred.id);
          setAddress(fromSaved(preferred));
          setSaveAddress(false);
        }
      })
      .catch(() => undefined);
  }, [user]);

  const items = useMemo(
    () => lines.map((l) => ({ product_id: l.productId, quantity: l.quantity, options: l.options ?? {} })),
    [lines],
  );

  // Price with the destination, so tax and shipping are exact.
  const validEmail = EMAIL_RE.test(email.trim());
  useEffect(() => {
    if (!items.length) return;
    const timer = setTimeout(() => {
      apiFetch<Quote>("/cart/quote", {
        method: "POST",
        body: JSON.stringify({
          items,
          coupon: coupon || undefined,
          email: validEmail ? email.trim() : undefined,
          destination: { country: address.country, region: address.region || undefined, postal_code: address.postal_code || undefined },
          lang: locale,
        }),
      })
        .then(setQuote)
        .catch(() => undefined);
    }, 350);
    return () => clearTimeout(timer);
  }, [items, coupon, address.country, address.region, address.postal_code, validEmail, email, locale]);

  // A cart snapshot for the "you left something" reminder — only with the shopper's permission.
  useEffect(() => {
    if (!items.length) return;
    const timer = setTimeout(() => {
      apiFetch<{ token: string }>("/cart/sync", {
        method: "POST",
        body: JSON.stringify({
          token: readToken() ?? undefined,
          items,
          coupon: coupon || undefined,
          email: reminders && validEmail ? email.trim() : undefined,
          reminders_ok: reminders && validEmail,
          checkout_started: true,
          locale,
        }),
      })
        .then((r) => saveToken(r.token))
        .catch(() => undefined);
    }, 800);
    return () => clearTimeout(timer);
  }, [items, coupon, reminders, validEmail, email, locale]);

  if (lines.length === 0 && stage === "form") {
    return (
      <EmptyState title={t.checkout.empty}>
        <Link href={href("/shop")} className="underline">
          {t.cart.continue}
        </Link>
      </EmptyState>
    );
  }

  const guestBlocked = !authLoading && !user && config && !config.guest_checkout;
  const set = (key: keyof AddressForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setAddress((a) => ({ ...a, [key]: e.target.value }));
    setSavedId("new");
  };

  function validate() {
    const next: typeof errors = {};
    if (!EMAIL_RE.test(email.trim())) next.email = t.checkout.required;
    for (const key of REQUIRED) if (!address[key].trim()) next[key] = t.checkout.required;
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setProblem(null);
    if (!validate()) {
      setProblem(t.checkout.fixErrors);
      return;
    }
    setStage("placing");
    const clean = (v: string) => v.trim() || null;
    try {
      const result = await apiFetch<CheckoutResult>("/checkout", {
        method: "POST",
        body: JSON.stringify({
          items,
          coupon: coupon || undefined,
          email: email.trim(),
          phone: clean(address.phone),
          shipping_address: {
            full_name: address.full_name.trim(),
            company: clean(address.company),
            line1: address.line1.trim(),
            line2: clean(address.line2),
            city: address.city.trim(),
            region: clean(address.region),
            postal_code: address.postal_code.trim(),
            country: address.country,
            phone: clean(address.phone),
          },
          notes: clean(notes),
          payment_method: method,
          locale,
          captcha_token: captcha,
          idempotency_key: idempotencyKey.current,
          cart_token: readToken() ?? undefined,
          marketing_opt_in: marketing,
          reminders_ok: reminders,
          save_address: !!user && savedId === "new" && saveAddress,
        }),
      });
      const token = result.order.access_token;
      if (result.payment.status === "redirect" && result.payment.redirect_url) {
        setStage("redirecting");
        clear();
        saveToken(null);
        window.location.assign(result.payment.redirect_url);
        return;
      }
      clear();
      saveToken(null);
      router.push(href(`/order/${token}?placed=1`));
    } catch (err) {
      setStage("form");
      setCaptchaKey((k) => k + 1); // tokens are single-use
      setProblem(err instanceof ApiRequestError ? err.message : t.cart.pricesUnavailable);
    }
  }

  const countries = config?.shipping_countries ?? ["US"];
  const deliverable = quote ? quote.shipping.deliverable : true;
  const busy = stage !== "form";

  return (
    <form onSubmit={submit} noValidate className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="space-y-10">
        {!user && !authLoading && (
          <p className="text-sm text-muted">
            {t.checkout.haveAccount}{" "}
            <Link href={href(`/login?next=${encodeURIComponent(href("/checkout"))}`)} className="underline">
              {t.checkout.signIn}
            </Link>
          </p>
        )}
        {guestBlocked && <Alert tone="danger">{t.checkout.accountRequired}</Alert>}

        <fieldset className="space-y-4" disabled={busy}>
          <legend className="mb-2 font-serif text-2xl">{t.checkout.contact}</legend>
          <Field label={t.checkout.email} error={errors.email}>
            {(p) => (
              <Input {...p} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            )}
          </Field>
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} className="mt-0.5 size-4 accent-[var(--color-accent)]" />
            <span>{t.checkout.marketing}</span>
          </label>
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" checked={reminders} onChange={(e) => setReminders(e.target.checked)} className="mt-0.5 size-4 accent-[var(--color-accent)]" />
            <span>{t.checkout.reminders}</span>
          </label>
        </fieldset>

        <fieldset className="space-y-4" disabled={busy}>
          <legend className="mb-2 font-serif text-2xl">{t.checkout.shipping}</legend>
          {saved.length > 0 && (
            <Field label={t.checkout.savedAddress}>
              {(p) => (
                <Select
                  {...p}
                  value={String(savedId)}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === "new") {
                      setSavedId("new");
                      setAddress({ ...EMPTY_ADDRESS, country: countries[0] ?? "US" });
                      return;
                    }
                    const a = saved.find((x) => String(x.id) === v);
                    if (a) {
                      setSavedId(a.id);
                      setAddress(fromSaved(a));
                    }
                  }}
                >
                  {saved.map((a) => (
                    <option key={a.id} value={a.id}>
                      {[a.label, a.full_name, a.line1, a.city].filter(Boolean).join(", ")}
                    </option>
                  ))}
                  <option value="new">{t.checkout.newAddress}</option>
                </Select>
              )}
            </Field>
          )}
          <Field label={t.addresses.fullName} error={errors.full_name}>
            {(p) => <Input {...p} autoComplete="name" required value={address.full_name} onChange={set("full_name")} />}
          </Field>
          <Field label={`${t.addresses.company} ${t.addresses.optional}`}>
            {(p) => <Input {...p} autoComplete="organization" value={address.company} onChange={set("company")} />}
          </Field>
          <Field label={t.addresses.line1} error={errors.line1}>
            {(p) => <Input {...p} autoComplete="address-line1" required value={address.line1} onChange={set("line1")} />}
          </Field>
          <Field label={`${t.addresses.line2} ${t.addresses.optional}`}>
            {(p) => <Input {...p} autoComplete="address-line2" value={address.line2} onChange={set("line2")} />}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t.addresses.city} error={errors.city}>
              {(p) => <Input {...p} autoComplete="address-level2" required value={address.city} onChange={set("city")} />}
            </Field>
            <Field label={t.addresses.region}>
              {(p) => <Input {...p} autoComplete="address-level1" value={address.region} onChange={set("region")} />}
            </Field>
            <Field label={t.addresses.postalCode} error={errors.postal_code}>
              {(p) => <Input {...p} autoComplete="postal-code" required value={address.postal_code} onChange={set("postal_code")} />}
            </Field>
            <Field label={t.addresses.country} error={!deliverable ? t.checkout.notDeliverable : undefined}>
              {(p) => (
                <Select {...p} autoComplete="country" value={address.country} onChange={set("country")}>
                  {countries.map((c) => (
                    <option key={c} value={c}>
                      {countryName(c, locale)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Field label={`${t.addresses.phone} ${t.addresses.optional}`} hint={t.addresses.phoneHint}>
            {(p) => <Input {...p} type="tel" autoComplete="tel" value={address.phone} onChange={set("phone")} />}
          </Field>
          {user && savedId === "new" && (
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" checked={saveAddress} onChange={(e) => setSaveAddress(e.target.checked)} className="mt-0.5 size-4 accent-[var(--color-accent)]" />
              <span>{t.checkout.saveAddress}</span>
            </label>
          )}
          <Field label={`${t.checkout.notes} ${t.addresses.optional}`} hint={t.checkout.notesHint}>
            {(p) => <Textarea {...p} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} />}
          </Field>
        </fieldset>

        <fieldset className="space-y-3" disabled={busy}>
          <legend className="mb-2 font-serif text-2xl">{t.checkout.payment}</legend>
          {(config?.payment_methods ?? []).map((m) => {
            const key = m as keyof typeof t.checkout.methods;
            return (
              <label
                key={m}
                className={cn(
                  "flex cursor-pointer gap-3 rounded-[var(--radius-card)] border px-4 py-3.5 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent",
                  method === m ? "border-accent bg-accent-soft" : "border-line bg-surface",
                )}
              >
                <input type="radio" name="payment" value={m} checked={method === m} onChange={() => setMethod(m)} className="mt-1 size-4 accent-[var(--color-accent)]" />
                <span>
                  <span className="block font-medium">{t.checkout.methods[key] ?? m}</span>
                  <span className="block text-sm text-muted">{t.checkout.methodHints[key] ?? ""}</span>
                </span>
              </label>
            );
          })}
        </fieldset>

        {!user && (
          <Turnstile action="checkout" onToken={setCaptcha} resetKey={captchaKey} locale={locale} label={t.auth.captcha} />
        )}
      </div>

      <aside aria-label={t.checkout.summary} className="h-fit space-y-5 rounded-[var(--radius-card)] border border-line bg-surface p-6 lg:sticky lg:top-24">
        <h2 className="text-2xl">{t.checkout.summary}</h2>
        <ul className="space-y-3">
          {lines.map((l) => (
            <li key={l.key} className="flex items-center gap-3 text-sm">
              <div className="relative size-14 shrink-0 overflow-hidden rounded-md bg-sand">
                <ProductImage src={l.image} alt="" sizes="56px" className="object-contain" />
              </div>
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2">{l.title}</span>
                {l.quantity > 1 && <span className="text-muted"> × {l.quantity}</span>}
              </span>
              <span className="tabular-nums">{formatPrice(l.price * l.quantity, l.currency, locale)}</span>
            </li>
          ))}
        </ul>
        <CouponForm />
        <CartTotals quote={quote} />
        {quote?.messages.length ? (
          <ul className="space-y-1 text-sm text-danger" role="alert">
            {quote.messages.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        ) : null}
        {problem && <Alert tone="danger">{problem}</Alert>}
        <Button type="submit" size="lg" className="w-full" disabled={busy || !method || !!guestBlocked || !deliverable || !!quote?.blocking}>
          {stage === "placing" ? t.checkout.placing : stage === "redirecting" ? t.checkout.redirecting : t.checkout.place}
        </Button>
        <p className="text-xs text-muted">{t.checkout.terms}</p>
        <ButtonLink href={href("/cart")} variant="ghost" size="sm" className="w-full">
          {t.checkout.back}
        </ButtonLink>
        {stage !== "form" && (
          <p role="status" className="sr-only">
            {stage === "placing" ? t.checkout.placing : t.checkout.redirecting}
          </p>
        )}
      </aside>
    </form>
  );
}
