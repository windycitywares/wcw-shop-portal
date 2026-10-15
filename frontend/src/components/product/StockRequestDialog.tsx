"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { attrKey, attrValue } from "@/i18n/attributes";
import { useI18n } from "@/i18n/client";
import { track } from "@/lib/analytics";
import { useAuth } from "@/lib/auth";
import { useCart } from "@/lib/cart";
import { ApiRequestError } from "@/lib/client-api";
import { stockRequests } from "@/lib/engagement";
import type { Product, ProductDetail } from "@/lib/types";
import { attributeList, displayPrice, formatPrice } from "@/lib/utils";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";

/** The choices a product offers, the same way the server works them out (app/domain/stock_requests.py). */
export function optionGroups(product: ProductDetail): { key: string; values: string[] }[] {
  const groups = new Map<string, string[]>();
  if (product.variants.length) {
    for (const v of product.variants) {
      for (const [key, value] of Object.entries(v.attributes)) {
        const list = groups.get(key) ?? [];
        for (const item of attributeList(value)) if (!list.includes(item)) list.push(item);
        groups.set(key, list);
      }
    }
  } else {
    for (const [key, value] of Object.entries(product.attributes)) {
      if (Array.isArray(value) && value.length > 1) groups.set(key, attributeList(value));
    }
  }
  return [...groups].map(([key, values]) => ({ key, values }));
}

const buyable = (p: Product) =>
  (p.stock_status === "in_stock" && (p.stock_quantity == null || p.stock_quantity > 0)) || p.stock_status === "backorder" || p.stock_status === "preorder";

/** Which product a choice is, and whether it can be bought now. variant undefined + sold=false = not a combination we sell. */
function lookup(product: ProductDetail, chosen: Record<string, string>): { item?: Product; sold: boolean; available: boolean } {
  if (!product.variants.length) return { item: product, sold: true, available: buyable(product) };
  const match = product.variants.find((v) =>
    Object.entries(chosen).every(([k, val]) => v.attributes[k] !== undefined && attributeList(v.attributes[k]).includes(val)),
  );
  return match ? { item: match, sold: true, available: buyable(match) } : { sold: false, available: false };
}

type Done = { kind: "restock" | "request"; already: boolean } | null;

/**
 * "Notify me when it's available" and "Ask for another combination", in one dialog. Signed-in customers only: the
 * request is linked to their account (and email). A combination that is in stock can be added to the cart from here.
 */
export function StockRequestDialog({
  product,
  open,
  onOpenChange,
  initial,
  mode,
}: {
  product: ProductDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The choice on the product page when the dialog opens. */
  initial: Record<string, string>;
  mode: "notify" | "other";
}) {
  const { t, fmt, href, locale } = useI18n();
  const { user, loading } = useAuth();
  const { add } = useCart();
  const groups = useMemo(() => optionGroups(product), [product]);
  const [chosen, setChosen] = useState<Record<string, string>>(initial);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Done>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setChosen({ ...Object.fromEntries(groups.map((g) => [g.key, g.values[0]])), ...initial });
      setNote("");
      setDone(null);
      setProblem(null);
    }
  }, [open, initial, groups]);

  const state = lookup(product, chosen);
  const itemName = [product.title, Object.values(chosen).map((v) => attrValue(t, v)).join(", ")].filter(Boolean).join(" — ");
  const here = typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : href(`/product/${product.slug}`);
  const loginHref = `${href("/login")}?next=${encodeURIComponent(here)}`;

  function addToCart() {
    if (!state.item) return;
    const variant = product.variants.length ? state.item : undefined;
    onOpenChange(false);
    add(
      {
        productId: state.item.id,
        slug: product.slug,
        sku: state.item.sku,
        title: product.title,
        variant: variant ? Object.values(variant.attributes).map((a) => attributeList(a).join("/")).join(", ") : undefined,
        price: displayPrice(state.item).amount,
        currency: state.item.currency,
        image: (state.item.images[0] ?? product.images[0])?.url,
        options: !product.variants.length && groups.length ? chosen : undefined,
      },
      1,
    );
  }

  async function submit() {
    setBusy(true);
    setProblem(null);
    try {
      const r = await stockRequests.create(product.id, chosen, note, locale);
      track("notify_me", { product_id: state.item?.id ?? product.id });
      setDone({ kind: r.kind, already: r.already });
    } catch (err) {
      setProblem(err instanceof ApiRequestError ? err.message : t.auth.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-night/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90dvh] w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col overflow-y-auto rounded-[var(--radius-card)] bg-canvas p-6 shadow-xl focus:outline-none">
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="font-serif text-2xl font-light">
              {!loading && !user ? t.stockRequest.signInTitle : mode === "other" ? t.stockRequest.titleOther : t.stockRequest.title}
            </Dialog.Title>
            <Dialog.Close className="-mr-2 -mt-1 grid size-10 shrink-0 place-items-center rounded-full hover:bg-sand">
              <span aria-hidden="true" className="text-xl leading-none">
                ×
              </span>
              <span className="sr-only">{t.stockRequest.close}</span>
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-1 text-sm text-muted">{product.title}</Dialog.Description>

          {loading ? (
            <div className="skeleton mt-6 h-24" />
          ) : !user ? (
            <div className="mt-5 space-y-5">
              <p className="text-[0.9375rem] leading-relaxed">{t.stockRequest.signInText}</p>
              <div className="flex flex-wrap gap-3">
                <ButtonLink href={loginHref}>{t.stockRequest.signIn}</ButtonLink>
                <ButtonLink href={`${loginHref}&mode=register`} variant="secondary">
                  {t.stockRequest.createAccount}
                </ButtonLink>
              </div>
            </div>
          ) : done ? (
            <div className="mt-5 space-y-5">
              <p role="status" className="rounded-[var(--radius-card)] border border-line bg-surface p-4 text-[0.9375rem] leading-relaxed">
                {done.already
                  ? fmt(t.stockRequest.already, { email: user.email })
                  : fmt(done.kind === "request" ? t.stockRequest.doneRequest : t.stockRequest.doneRestock, { email: user.email, item: itemName })}
              </p>
              <div className="flex flex-wrap gap-3">
                <ButtonLink href={`${href("/account")}#my-stock-requests`} variant="secondary" onClick={() => onOpenChange(false)}>
                  {t.stockRequest.seeRequests}
                </ButtonLink>
                <Button variant="ghost" onClick={() => onOpenChange(false)}>
                  {t.stockRequest.close}
                </Button>
              </div>
            </div>
          ) : (
            <div className="mt-5 space-y-5">
              <p className="text-sm">{t.stockRequest.intro}</p>
              {groups.map((g) => (
                <div key={g.key}>
                  <label htmlFor={`req-${g.key}`} className="mb-1.5 block text-sm font-medium">
                    {attrKey(t, g.key)}
                  </label>
                  <select
                    id={`req-${g.key}`}
                    value={chosen[g.key] ?? ""}
                    onChange={(e) => setChosen((c) => ({ ...c, [g.key]: e.target.value }))}
                    className="h-11 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
                  >
                    {g.values.map((v) => (
                      <option key={v} value={v}>
                        {attrValue(t, v)}
                      </option>
                    ))}
                  </select>
                </div>
              ))}

              <p
                aria-live="polite"
                className={`rounded-[var(--radius-card)] border p-3 text-sm ${state.available ? "border-success/40 bg-success/10" : "border-line bg-surface"}`}
              >
                {state.available ? t.stockRequest.available : state.sold ? t.stockRequest.outOfStock : t.stockRequest.notSold}
                {state.available && state.item && (
                  <span className="ml-1 font-medium tabular-nums">{formatPrice(displayPrice(state.item).amount, state.item.currency, locale)}</span>
                )}
              </p>

              {state.available ? (
                <Button className="w-full" onClick={addToCart}>
                  {t.stockRequest.addToCart}
                </Button>
              ) : (
                <>
                  <div>
                    <label htmlFor="req-note" className="mb-1.5 block text-sm font-medium">
                      {t.stockRequest.note}
                    </label>
                    <Textarea
                      id="req-note"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      maxLength={1000}
                      rows={3}
                      placeholder={t.stockRequest.notePlaceholder}
                    />
                  </div>
                  {problem && (
                    <p role="alert" className="text-sm text-danger">
                      {problem}
                    </p>
                  )}
                  <Button className="w-full" onClick={submit} disabled={busy}>
                    {busy ? t.stockRequest.sending : state.sold ? t.stockRequest.submitRestock : t.stockRequest.submitRequest}
                  </Button>
                </>
              )}
              <p className="text-xs text-muted">
                <Link href={`${href("/account")}#my-stock-requests`} className="underline underline-offset-4" onClick={() => onOpenChange(false)}>
                  {t.stockRequest.seeRequests}
                </Link>
              </p>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
