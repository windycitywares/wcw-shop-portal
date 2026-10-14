"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { apiFetch } from "@/lib/client-api";
import { Button } from "@/components/ui/Button";
import { Alert, Container } from "@/components/ui/misc";

/**
 * /unsubscribe?token=… from any marketing email. The shopper confirms with a click, so link scanners in mail
 * systems (which open every link) can't unsubscribe people by accident.
 */
export default function UnsubscribePage() {
  const { t, href } = useI18n();
  const [token, setToken] = useState<string | null>(null);
  const [state, setState] = useState<"ready" | "working" | "done" | "invalid">("ready");

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token"));
  }, []);

  async function confirm() {
    if (!token) return;
    setState("working");
    try {
      await apiFetch("/newsletter/unsubscribe", { method: "POST", body: JSON.stringify({ token }) });
      setState("done");
    } catch {
      setState("invalid");
    }
  }

  return (
    <Container className="max-w-xl py-12 sm:py-16">
      <h1 className="text-5xl">{t.unsubscribe.title}</h1>
      {state === "done" ? (
        <Alert tone="success" className="mt-6">
          {t.unsubscribe.done}
        </Alert>
      ) : state === "invalid" ? (
        <Alert tone="danger" className="mt-6">
          {t.unsubscribe.invalid}
        </Alert>
      ) : token ? (
        <>
          <p className="mt-3 text-muted">{t.unsubscribe.intro}</p>
          <Button size="lg" className="mt-6" onClick={confirm} disabled={state === "working"}>
            {state === "working" ? t.unsubscribe.working : t.unsubscribe.confirm}
          </Button>
        </>
      ) : (
        <p className="mt-3 text-muted">{t.unsubscribe.missing}</p>
      )}
      <p className="mt-10 text-sm">
        <Link href={href("/shop")} className="underline">
          {t.unsubscribe.back}
        </Link>
      </p>
    </Container>
  );
}
