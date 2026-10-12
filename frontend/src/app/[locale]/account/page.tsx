"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { isStaff, useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert, Container } from "@/components/ui/misc";

export default function AccountPage() {
  const { user, loading, logout, refresh, changePassword } = useAuth();
  const router = useRouter();
  const { t, href } = useI18n();
  const [saved, setSaved] = useState("");
  const [pwMessage, setPwMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace(`${href("/login")}?next=${encodeURIComponent(href("/account"))}`);
  }, [loading, user, router, href]);

  if (!user) return <Container className="py-16 text-muted">{t.account.loading}</Container>;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const full_name = String(new FormData(e.currentTarget).get("full_name") || "") || null;
    await apiFetch("/auth/me", { method: "PATCH", body: JSON.stringify({ full_name }) });
    await refresh();
    setSaved(t.account.saved);
  }

  async function onChangePassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const next = String(fd.get("new_password"));
    if (next !== String(fd.get("confirm_password"))) {
      setPwMessage({ tone: "danger", text: t.account.mismatch });
      return;
    }
    try {
      await changePassword(String(fd.get("current_password")), next);
      form.reset();
      setPwMessage({ tone: "success", text: t.account.changed });
    } catch (err) {
      setPwMessage({ tone: "danger", text: err instanceof Error ? err.message : t.account.changeFailed });
    }
  }

  return (
    <Container className="max-w-2xl py-12">
      <h1 className="text-5xl">{t.account.title}</h1>
      <p className="mt-2 text-muted">{user.email}</p>
      {isStaff(user) && (
        <ButtonLink href="/admin" variant="secondary" size="sm" className="mt-4">
          {t.account.goAdmin}
        </ButtonLink>
      )}

      <section aria-labelledby="profile-heading" className="mt-10 rounded-[var(--radius-card)] border border-line bg-surface p-6">
        <h2 id="profile-heading" className="text-2xl">
          {t.account.profile}
        </h2>
        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <Field label={t.account.name}>{(p) => <Input {...p} name="full_name" defaultValue={user.full_name ?? ""} />}</Field>
          {saved && <Alert tone="success">{saved}</Alert>}
          <Button type="submit">{t.account.save}</Button>
        </form>
      </section>

      <section aria-labelledby="password-heading" className="mt-6 rounded-[var(--radius-card)] border border-line bg-surface p-6">
        <h2 id="password-heading" className="text-2xl">
          {t.account.password}
        </h2>
        <form onSubmit={onChangePassword} className="mt-4 space-y-4">
          <Field label={t.account.current}>
            {(p) => <Input {...p} name="current_password" type="password" required autoComplete="current-password" />}
          </Field>
          <Field label={t.account.new} hint={t.account.newHint}>
            {(p) => <Input {...p} name="new_password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" />}
          </Field>
          <Field label={t.account.confirm}>
            {(p) => <Input {...p} name="confirm_password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" />}
          </Field>
          {pwMessage && <Alert tone={pwMessage.tone}>{pwMessage.text}</Alert>}
          <Button type="submit">{t.account.change}</Button>
        </form>
      </section>

      <section aria-labelledby="orders-heading" className="mt-6 rounded-[var(--radius-card)] border border-line bg-surface p-6">
        <h2 id="orders-heading" className="text-2xl">
          {t.account.orders}
        </h2>
        <p className="mt-2 text-sm text-muted">
          {t.account.ordersEmpty}{" "}
          <Link href={href("/shop")} className="underline">
            {t.account.keepShopping}
          </Link>
        </p>
      </section>

      <Button
        variant="ghost"
        className="mt-8"
        onClick={() => {
          logout();
          router.push(href("/"));
        }}
      >
        {t.account.signOut}
      </Button>
    </Container>
  );
}
