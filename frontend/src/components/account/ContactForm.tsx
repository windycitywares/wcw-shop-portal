"use client";

import { useState } from "react";
import { useI18n } from "@/i18n/client";
import { sendContact } from "@/lib/account";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { Turnstile } from "@/components/ui/Turnstile";

export function ContactForm() {
  const { t, locale, fmt } = useI18n();
  const { user } = useAuth();
  const [captcha, setCaptcha] = useState<string | null>(null);
  const [captchaKey, setCaptchaKey] = useState(0);
  const [sentTo, setSentTo] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const email = String(fd.get("email")).trim();
    setBusy(true);
    setError("");
    try {
      await sendContact({
        name: String(fd.get("name")).trim(),
        email,
        subject: String(fd.get("subject")).trim(),
        message: String(fd.get("message")).trim(),
        order_number: String(fd.get("order_number") || "").trim() || null,
        locale,
        captcha_token: captcha,
        website: String(fd.get("website") || ""),
      });
      form.reset();
      setSentTo(email);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.auth.error);
    } finally {
      setBusy(false);
      setCaptchaKey((k) => k + 1); // tokens are single-use
    }
  }

  if (sentTo) {
    return (
      <div className="space-y-6" aria-live="polite">
        <Alert tone="success">{fmt(t.contact.sent, { email: sentTo })}</Alert>
        <Button variant="secondary" onClick={() => setSentTo("")}>
          {t.contact.sendAnother}
        </Button>
      </div>
    );
  }

  const opt = (label: string) => `${label} ${t.addresses.optional}`;
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {error && <Alert tone="danger">{error}</Alert>}
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label={t.contact.name}>
          {(p) => <Input {...p} name="name" required maxLength={200} autoComplete="name" defaultValue={user?.full_name ?? ""} />}
        </Field>
        <Field label={t.contact.email}>
          {(p) => <Input {...p} name="email" type="email" required maxLength={320} autoComplete="email" defaultValue={user?.email ?? ""} />}
        </Field>
      </div>
      <div className="grid gap-5 sm:grid-cols-[1fr_12rem]">
        <Field label={t.contact.subject}>{(p) => <Input {...p} name="subject" required maxLength={200} />}</Field>
        <Field label={opt(t.contact.orderNumber)}>{(p) => <Input {...p} name="order_number" maxLength={32} />}</Field>
      </div>
      <Field label={t.contact.message} hint={t.contact.messageHint}>
        {(p) => <Textarea {...p} name="message" required minLength={10} maxLength={5000} rows={7} />}
      </Field>
      {/* Honeypot for bots: hidden from people and screen readers. */}
      <div aria-hidden="true" className="absolute -left-[10000px] h-px w-px overflow-hidden">
        <label>
          Website <input name="website" type="text" tabIndex={-1} autoComplete="off" />
        </label>
      </div>
      <Turnstile onToken={setCaptcha} resetKey={captchaKey} locale={locale} label={t.auth.captcha} />
      <Button type="submit" size="lg" disabled={busy}>
        {busy ? t.contact.sending : t.contact.send}
      </Button>
    </form>
  );
}
