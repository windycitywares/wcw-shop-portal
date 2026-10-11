"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { isStaff, useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert, Container } from "@/components/ui/misc";

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "register">("signin");
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
        mode === "signin" ? await login(email, password) : await register(email, password, String(data.get("name") || ""));
      const next = new URLSearchParams(window.location.search).get("next");
      router.push(next && next.startsWith("/") ? next : isStaff(user) ? "/admin" : "/account");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Container className="max-w-md py-16">
      <h1 className="text-4xl">{mode === "signin" ? "Sign in" : "Create an account"}</h1>
      <form onSubmit={onSubmit} className="mt-8 space-y-5" noValidate={false}>
        {error && <Alert tone="danger">{error}</Alert>}
        {mode === "register" && (
          <Field label="Name">{(p) => <Input {...p} name="name" autoComplete="name" />}</Field>
        )}
        <Field label="Email">{(p) => <Input {...p} name="email" type="email" required autoComplete="email" />}</Field>
        <Field label="Password" hint={mode === "register" ? "At least 8 characters." : undefined}>
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
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        {mode === "signin" ? "New here? " : "Already have an account? "}
        <button
          type="button"
          className="font-medium text-accent underline"
          onClick={() => {
            setMode(mode === "signin" ? "register" : "signin");
            setError("");
          }}
        >
          {mode === "signin" ? "Create an account" : "Sign in"}
        </button>
      </p>
    </Container>
  );
}
