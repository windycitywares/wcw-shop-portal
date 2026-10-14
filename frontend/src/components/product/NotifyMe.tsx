"use client";

import { useState } from "react";
import { useI18n } from "@/i18n/client";
import { useAuth } from "@/lib/auth";
import { ApiRequestError } from "@/lib/client-api";
import { notifyMe } from "@/lib/engagement";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";

/** Shown instead of "Add to cart" when a design is sold out: one email when it's back. */
export function NotifyMe({ productId }: { productId: number }) {
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const [email, setEmail] = useState(user?.email ?? "");
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [problem, setProblem] = useState<string | null>(null);

  if (state === "done") {
    return (
      <p role="status" className="rounded-[var(--radius-card)] border border-line bg-surface p-4 text-sm">
        {t.notify.done}
      </p>
    );
  }
  return (
    <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4">
      <p className="font-serif text-lg">{t.notify.title}</p>
      <p className="mt-1 text-sm text-muted">{t.notify.hint}</p>
      <div className="mt-3 flex gap-2">
        <label htmlFor="notify-email" className="sr-only">
          {t.notify.email}
        </label>
        <Input
          id="notify-email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t.notify.email}
          className="min-w-0 flex-1"
        />
        <Button
          type="button"
          disabled={state === "sending" || !email.includes("@")}
          onClick={async () => {
            setState("sending");
            setProblem(null);
            try {
              await notifyMe(productId, email.trim(), locale);
              setState("done");
            } catch (err) {
              setProblem(err instanceof ApiRequestError ? err.message : t.auth.error);
              setState("idle");
            }
          }}
        >
          {t.notify.submit}
        </Button>
      </div>
      {problem && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {problem}
        </p>
      )}
    </div>
  );
}
