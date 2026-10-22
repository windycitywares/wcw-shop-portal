"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { isStaff, useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert, Container } from "@/components/ui/misc";
import { Turnstile } from "@/components/ui/Turnstile";

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const { t, href, locale } = useI18n();
  const [captcha, setCaptcha] = useState<string | null>(null);
  const [captchaKey, setCaptchaKey] = useState(0);
  const [mode, setMode] = useState<"signin" | "register">("signin");
  useEffect(() => {
    // "Create an account" links (e.g. from the notify-me dialog) open the form in sign-up mode.
    if (new URLSearchParams(window.location.search).get("mode") === "register") setMode("register");
  }, []);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const email = String(data.get("email"));
    const password = String(data.get("password"));
    setBusy(true);
    setError("");
    try {
      const user =
        mode === "signin"
          ? await login(email, password)
          : await register(email, password, String(data.get("name") || ""), captcha, locale);
      const next = new URLSearchParams(window.location.search).get("next");
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : isStaff(user) ? "/admin" : href("/account"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t.auth.error);
      if (mode === "register") setCaptchaKey((k) => k + 1); // tokens are single-use
    } finally {
      setBusy(false);
    }
  }

  return (
    <Container className="max-w-md py-16 sm:py-24">
      <h1 className="text-5xl">{mode === "signin" ? t.auth.signIn : t.auth.createAccountTitle}</h1>
      <form onSubmit={onSubmit} className="mt-8 space-y-5" noValidate={false}>
        {error && <Alert tone="danger">{error}</Alert>}
        {mode === "register" && (
          <Field label={t.auth.name}>{(p) => <Input {...p} name="name" autoComplete="name" />}</Field>
        )}
        <Field label={t.auth.email}>{(p) => <Input {...p} name="email" type="email" required autoComplete="email" />}</Field>
        <Field label={t.auth.password} hint={mode === "register" ? t.auth.passwordHint : undefined}>
          {(p) => (
            <Input
              {...p}
              name="password"
              type="password"
              required
              minLength={mode === "register" ? 8 : undefined}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
            />
          )}
        </Field>
        {mode === "signin" ? (
          <p className="-mt-2 text-right text-sm">
            <Link href={href("/forgot-password")} className="text-accent underline underline-offset-2">
              {t.auth.forgot}
            </Link>
          </p>
        ) : (
          <Turnstile action="signup" onToken={setCaptcha} resetKey={captchaKey} locale={locale} label={t.auth.captcha} />
        )}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? t.auth.wait : mode === "signin" ? t.auth.signIn : t.auth.createAccount}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        {mode === "signin" ? t.auth.newHere : t.auth.haveAccount}{" "}
        <button
          type="button"
          className="font-medium text-accent underline"
          onClick={() => {
            setMode(mode === "signin" ? "register" : "signin");
            setError("");
          }}
        >
          {mode === "signin" ? t.auth.createAccountTitle : t.auth.signIn}
        </button>
      </p>
    </Container>
  );
}
