"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useI18n } from "@/i18n/client";
import { ApiRequestError, apiFetch } from "@/lib/client-api";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert, Container } from "@/components/ui/misc";

/** Find an order by number + email; the answer is the order's private page. */
export default function TrackOrderPage() {
  const { t, href } = useI18n();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setProblem(null);
    try {
      const res = await apiFetch<{ detail: string }>("/orders/lookup", {
        method: "POST",
        body: JSON.stringify({ number: String(fd.get("number")).trim(), email: String(fd.get("email")).trim() }),
      });
      router.push(href(`/order/${res.detail}`));
    } catch (err) {
      setProblem(err instanceof ApiRequestError ? err.message : t.auth.error);
      setBusy(false);
    }
  }

  return (
    <Container className="max-w-xl py-12 sm:py-16">
      <h1 className="text-5xl">{t.track.title}</h1>
      <p className="mt-3 text-muted">{t.track.intro}</p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <Field label={t.track.number} hint={t.track.numberHint}>
          {(p) => <Input {...p} name="number" required minLength={3} maxLength={32} autoComplete="off" />}
        </Field>
        <Field label={t.track.email}>
          {(p) => <Input {...p} name="email" type="email" required autoComplete="email" />}
        </Field>
        {problem && <Alert tone="danger">{problem}</Alert>}
        <Button type="submit" size="lg" disabled={busy}>
          {busy ? t.track.finding : t.track.submit}
        </Button>
      </form>
      <p className="mt-8 text-sm text-muted">
        <Link href={href("/account")} className="underline">
          {t.track.signedIn}
        </Link>
      </p>
    </Container>
  );
}
