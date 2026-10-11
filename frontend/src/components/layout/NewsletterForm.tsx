"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { Button } from "@/components/ui/Button";

export function NewsletterForm() {
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email") || "");
    setState("sending");
    try {
      const res = await apiFetch<{ detail: string }>("/newsletter", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setMessage(res.detail);
      setState("done");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Something went wrong");
      setState("error");
    }
  }

  return (
    <div className="mt-5">
      <form onSubmit={onSubmit} className="flex gap-2">
        <label htmlFor="newsletter-email" className="sr-only">
          Email address
        </label>
        <input
          id="newsletter-email"
          name="email"
          type="email"
          required
          autoComplete="email"
          placeholder="you@example.com"
          className="h-11 min-w-0 flex-1 rounded-full border border-line bg-surface px-4 text-sm focus-visible:border-accent"
        />
        <Button type="submit" disabled={state === "sending"}>
          {state === "sending" ? "Joining…" : "Subscribe"}
        </Button>
      </form>
      <p
        role="status"
        aria-live="polite"
        className={state === "error" ? "mt-2 text-sm text-danger" : "mt-2 text-sm text-success"}
      >
        {state === "done" || state === "error" ? message : ""}
      </p>
    </div>
  );
}
