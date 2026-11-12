"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

interface Environment {
  mode: "live" | "test";
  effective: "live" | "test";
  test_exists: boolean;
  stripe_test_configured: boolean;
}

/**
 * The Test / Real payments switch. It is the shop's Test mode (Admin → Test mode) seen from Payments:
 * test payments only ever touch the test copy of the data, so nothing mixes with real orders, stock or email.
 */
export function PaymentModeToggle({ stripeLive }: { stripeLive: boolean }) {
  const { push } = useToast();
  const { logout } = useAuth();
  const router = useRouter();
  const [env, setEnv] = useState<Environment | null>(null);
  const [error, setError] = useState("");
  const [ask, setAsk] = useState<"test" | "live" | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<"test" | "live" | null>(null);

  const load = useCallback(() => {
    apiFetch<Environment>("/admin/environment").then(setEnv, (e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const test = env?.effective === "test";
  const signOut = () => {
    logout();
    router.replace("/login?next=/admin/settings?tab=payments");
  };

  async function switchTo(mode: "test" | "live") {
    setBusy(true);
    try {
      await apiFetch<Environment>("/admin/environment/mode", { method: "PUT", body: JSON.stringify({ mode }) });
      setAsk(null);
      setDone(mode); // the switch signs everyone out, this page included
    } catch (e) {
      push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="mb-6">
      <PanelHeader
        title="Test payments"
        description="Try the whole checkout without taking real money. A test order is paid the same way a real one is, and it only exists in the test copy of the shop."
        actions={env && <Pill tone={test ? "warning" : "success"}>{test ? "Test payments on" : "Real payments"}</Pill>}
      />
      <PanelBody className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        {!env ? (
          <div className="skeleton h-16" />
        ) : (
          <>
            <div className="flex items-center justify-between gap-4">
              <div id="pay-mode-label">
                <p className="font-medium">{test ? "Test payments are on" : "Real payments are on"}</p>
                <p className="text-sm text-muted">
                  {test
                    ? env.stripe_test_configured
                      ? "Checkout uses Stripe's test mode: use card 4242 4242 4242 4242, any future date and any CVC. Nothing is charged."
                      : "Checkout uses a test card form: 4242 4242 4242 4242 pays, 4000 0000 0000 0002 is declined. Nothing is charged."
                    : stripeLive
                      ? "Customers pay by card through Stripe and money is taken."
                      : "Stripe isn't set up on the server yet, so checkout can't take payment. Turn on test payments to try it."}
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={test}
                aria-labelledby="pay-mode-label"
                disabled={busy}
                onClick={() => setAsk(test ? "live" : "test")}
                className={cn(
                  "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border border-line transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60",
                  test ? "bg-accent" : "bg-sand",
                )}
              >
                <span className={cn("inline-block size-5 rounded-full bg-surface shadow transition-transform", test ? "translate-x-6" : "translate-x-1")} />
              </button>
            </div>
            {test && (
              <Alert tone="info">
                The shop is working on test data. Real customers are not affected, but they also see this copy until you switch back. See{" "}
                <Link href="/admin/environment" className="underline">
                  Test mode
                </Link>{" "}
                for the test inbox and who may sign in.
              </Alert>
            )}
          </>
        )}
      </PanelBody>

      <ConfirmDialog
        open={ask !== null}
        title={ask === "test" ? "Turn on test payments?" : "Go back to real payments?"}
        message={
          ask === "test"
            ? "The live data is copied and the whole shop works on the copy until you switch back, so test orders never mix with real ones. Everyone is signed out and signs in again."
            : "The shop goes back to the real data and real payments straight away. The test data is kept until you delete it. Everyone is signed out and signs in again."
        }
        confirmLabel={ask === "test" ? "Turn on test payments" : "Use real payments"}
        tone="primary"
        busy={busy}
        onConfirm={() => ask && switchTo(ask)}
        onCancel={() => setAsk(null)}
      />
      <Modal open={done !== null} onClose={signOut} title={done === "test" ? "Test payments are on" : "Real payments are on"} description="Everyone has been signed out. Sign in again with your usual password.">
        <Button onClick={signOut}>Sign in again</Button>
      </Modal>
    </Panel>
  );
}
