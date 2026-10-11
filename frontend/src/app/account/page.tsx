"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { isStaff, useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert, Container } from "@/components/ui/misc";

export default function AccountPage() {
  const { user, loading, logout, refresh } = useAuth();
  const router = useRouter();
  const [saved, setSaved] = useState("");

  useEffect(() => {
    if (!loading && !user) router.replace("/login?next=/account");
  }, [loading, user, router]);

  if (!user) return <Container className="py-16 text-muted">Loading…</Container>;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const full_name = String(new FormData(e.currentTarget).get("full_name") || "") || null;
    await apiFetch("/auth/me", { method: "PATCH", body: JSON.stringify({ full_name }) });
    await refresh();
    setSaved("Saved.");
  }

  return (
    <Container className="max-w-2xl py-12">
      <h1 className="text-4xl">Your account</h1>
      <p className="mt-2 text-muted">{user.email}</p>
      {isStaff(user) && (
        <ButtonLink href="/admin" variant="secondary" size="sm" className="mt-4">
          Go to admin
        </ButtonLink>
      )}

      <section aria-labelledby="profile-heading" className="mt-10 rounded-[var(--radius-card)] border border-line bg-surface p-6">
        <h2 id="profile-heading" className="text-2xl">
          Profile
        </h2>
        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <Field label="Name">{(p) => <Input {...p} name="full_name" defaultValue={user.full_name ?? ""} />}</Field>
          {saved && <Alert tone="success">{saved}</Alert>}
          <Button type="submit">Save</Button>
        </form>
      </section>

      <section aria-labelledby="orders-heading" className="mt-6 rounded-[var(--radius-card)] border border-line bg-surface p-6">
        <h2 id="orders-heading" className="text-2xl">
          Orders
        </h2>
        <p className="mt-2 text-sm text-muted">
          Your order history will appear here once online checkout is live. <Link href="/shop" className="underline">Keep shopping</Link>
        </p>
      </section>

      <Button
        variant="ghost"
        className="mt-8"
        onClick={() => {
          logout();
          router.push("/");
        }}
      >
        Sign out
      </Button>
    </Container>
  );
}
