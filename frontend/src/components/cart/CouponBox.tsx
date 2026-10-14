"use client";

import { useState } from "react";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";
import type { Quote, QuoteProblem } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

/** The words for a code that can't be used (in the shopper's language when we have them, the API's otherwise). */
export function useProblemText() {
  const { t, fmt, locale } = useI18n();
  return (problem: QuoteProblem, currency: string) => {
    const known = t.cart.problems[problem.code];
    if (!known) return problem.message;
    const min = Number(problem.data.min);
    return fmt(known, { min: Number.isFinite(min) ? formatPrice(min, currency, locale) : (problem.data.min ?? "") });
  };
}

/**
 * Enter a discount code, see whether it works, take it off again. The code lives in the cart (so it follows the
 * shopper to checkout); the quote says what it does.
 */
export function CouponBox({ quote, quoteCoupon, loading }: { quote: Quote | null; quoteCoupon: string | null; loading: boolean }) {
  const { coupon, setCoupon } = useCart();
  const { t, fmt } = useI18n();
  const problemText = useProblemText();
  const [draft, setDraft] = useState("");

  if (coupon) {
    const answered = quote != null && quoteCoupon === coupon && !loading;
    const problem = answered ? quote.coupon_problem : null;
    return (
      <div className="space-y-2">
        {!answered ? (
          <Alert tone="info">{t.cart.applying}</Alert>
        ) : problem ? (
          <Alert tone={problem.code === "needs_email" ? "info" : "danger"}>{problemText(problem, quote.currency)}</Alert>
        ) : (
          <Alert tone="success">{fmt(t.cart.codeApplied, { code: coupon })}</Alert>
        )}
        <button type="button" onClick={() => setCoupon(null)} className="text-xs text-muted underline hover:text-ink">
          {fmt(t.cart.removeCode, { code: coupon })}
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!draft.trim()) return;
        setCoupon(draft);
        setDraft("");
      }}
    >
      <Field label={t.cart.codeLabel} hint={t.cart.codeHelp}>
        {(props) => (
          <div className="flex gap-2">
            <Input
              {...props}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              maxLength={60}
              className="flex-1 uppercase placeholder:normal-case"
            />
            <Button type="submit" variant="secondary" disabled={!draft.trim()}>
              {t.cart.apply}
            </Button>
          </div>
        )}
      </Field>
    </form>
  );
}
