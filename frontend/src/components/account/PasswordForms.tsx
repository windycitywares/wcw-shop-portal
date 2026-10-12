"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { passwordApi } from "@/lib/account";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

export function ForgotPasswordForm() {
  const { t, href, locale, fmt } = useI18n();
  const [sentTo, setSentTo] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email")).trim();
    setBusy(true);
    setError("");
    try {
      await passwordApi.forgot(email, locale);
      setSentTo(email);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.auth.error);
    } finally {
      setBusy(false);
    }
  }

  if (sentTo) {
    return (
      <div className="mt-8 space-y-6">
        <Alert tone="success">{fmt(t.password.sent, { email: sentTo })}</Alert>
        <Link href={href("/login")} className="inline-block text-sm text-accent underline underline-offset-2">
          {t.password.backToSignIn}
        </Link>
      </div>
    );
  }
  return (
    <form onSubmit={onSubmit} className="mt-8 space-y-5">
      {error && <Alert tone="danger">{error}</Alert>}
      <Field label={t.auth.email}>{(p) => <Input {...p} name="email" type="email" required autoComplete="email" />}</Field>
      <Button type="submit" size="lg" className="w-full" disabled={busy}>
        {busy ? t.password.sending : t.password.send}
      </Button>
      <p className="text-center text-sm">
        <Link href={href("/login")} className="text-accent underline underline-offset-2">
          {t.password.backToSignIn}
        </Link>
      </p>
    </form>
  );
}

export function ResetPasswordForm() {
  const { t, href } = useI18n();
  const [token, setToken] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Read the token, then drop it from the address bar so it isn't left in history or shared by accident.
    const tk = new URLSearchParams(window.location.search).get("token");
    setToken(tk ?? "");
    if (tk) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const next = String(fd.get("new_password"));
    if (next !== String(fd.get("confirm_password"))) {
      setError(t.password.mismatch);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await passwordApi.reset(token!, next);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.auth.error);
    } finally {
      setBusy(false);
    }
  }

  if (token === null) return null;
  if (!token) {
    return (
      <div className="mt-8 space-y-6">
        <Alert tone="danger">{t.password.missingToken}</Alert>
        <ButtonLink href={href("/forgot-password")} variant="secondary">
          {t.password.requestNew}
        </ButtonLink>
      </div>
    );
  }
  if (done) {
    return (
      <div className="mt-8 space-y-6">
        <Alert tone="success">{t.password.done}</Alert>
        <ButtonLink href={href("/login")}>{t.password.signInNow}</ButtonLink>
      </div>
    );
  }
  return (
    <form onSubmit={onSubmit} className="mt-8 space-y-5">
      {error && (
        <Alert tone="danger">
          {error}{" "}
          <Link href={href("/forgot-password")} className="underline">
            {t.password.requestNew}
          </Link>
        </Alert>
      )}
      <Field label={t.password.newPassword} hint={t.auth.passwordHint}>
        {(p) => <Input {...p} name="new_password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" />}
      </Field>
      <Field label={t.password.confirm}>
        {(p) => <Input {...p} name="confirm_password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" />}
      </Field>
      <Button type="submit" size="lg" className="w-full" disabled={busy}>
        {busy ? t.auth.wait : t.password.submit}
      </Button>
    </form>
  );
}
