"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { dateTime, timeAgo } from "@/components/admin/charts/format";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Environment {
  mode: "live" | "test";
  effective: "live" | "test";
  test_exists: boolean;
  test_synced_at: string | null;
  test_mail_to: string | null;
  test_login_emails: string[];
  test_size_bytes: number | null;
  out_of_date: boolean;
  changed_at: string | null;
  changed_by_email: string | null;
  stripe_test_configured: boolean;
  stats: { tables: number; rows: number; seconds: number } | null;
}

type Confirm = "test" | "live" | "sync" | "delete" | null;

const size = (bytes: number | null) => (bytes == null ? "—" : bytes > 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`);

const CONFIRM: Record<Exclude<Confirm, null>, { title: string; message: string; label: string; tone: "danger" | "primary" }> = {
  test: {
    title: "Switch the shop to test mode?",
    message:
      "The live data is copied and the whole shop (storefront, admin and scheduled jobs) works on the copy until you switch back. Shoppers visiting meanwhile use the copy too. Everyone is signed out and signs in again with the same password.",
    label: "Switch to test",
    tone: "primary",
  },
  live: {
    title: "Switch back to live data?",
    message: "The shop goes back to the real data straight away. The test data is kept until you delete it. Everyone is signed out and signs in again.",
    label: "Switch to live",
    tone: "primary",
  },
  sync: {
    title: "Copy the live data again?",
    message: "Everything done during testing (orders, accounts, changes) is replaced by a fresh copy of the live data. This can't be undone.",
    label: "Copy live data",
    tone: "danger",
  },
  delete: {
    title: "Delete the test data?",
    message: "The test copy and everything testers did in it are removed for good. The live data isn't touched.",
    label: "Delete test data",
    tone: "danger",
  },
};

/** Live / Test switch (admins only). See docs/DEPLOYMENT.md → "Test mode". */
export default function AdminEnvironment() {
  const { push } = useToast();
  const { logout } = useAuth();
  const router = useRouter();
  const [env, setEnv] = useState<Environment | null>(null);
  const [mailTo, setMailTo] = useState("");
  const [loginsText, setLoginsText] = useState("");
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [busy, setBusy] = useState(false);
  const [switched, setSwitched] = useState<"live" | "test" | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    apiFetch<Environment>("/admin/environment").then(
      (d) => {
        setEnv(d);
        setMailTo(d.test_mail_to ?? "");
        setLoginsText((d.test_login_emails ?? []).join("\n"));
        setError("");
      },
      (e) => setError(e.message),
    );
  }, []);
  useEffect(load, [load]);

  async function run(action: Exclude<Confirm, null>) {
    setBusy(true);
    try {
      if (action === "test" || action === "live") {
        await apiFetch<Environment>("/admin/environment/mode", { method: "PUT", body: JSON.stringify({ mode: action }) });
        setConfirm(null);
        setSwitched(action); // the switch signs everyone out, this page included
        return;
      }
      if (action === "sync") {
        const d = await apiFetch<Environment>("/admin/environment/sync", { method: "POST" });
        setEnv(d);
        push({ title: "Live data copied", description: d.stats ? `${d.stats.tables} tables, ${d.stats.rows.toLocaleString()} rows in ${d.stats.seconds} s` : undefined });
      } else {
        await apiFetch("/admin/environment/test-data", { method: "DELETE" });
        push({ title: "Test data deleted" });
        load();
      }
      setConfirm(null);
    } catch (e) {
      push({ title: "That didn't work", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  async function saveMailTo(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const d = await apiFetch<Environment>("/admin/environment/mail-to", { method: "PUT", body: JSON.stringify({ email: mailTo.trim() || null }) });
      setEnv(d);
      push({ title: "Test inbox saved", description: d.test_mail_to ?? "Emails won't be sent in test mode" });
    } catch (err) {
      push({ title: "That didn't work", description: err instanceof Error ? err.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  async function saveLogins(e: React.FormEvent) {
    e.preventDefault();
    const emails = loginsText
      .split(/[\s,;]+/)
      .map((x) => x.trim())
      .filter(Boolean);
    setBusy(true);
    try {
      const d = await apiFetch<Environment>("/admin/environment/test-logins", { method: "PUT", body: JSON.stringify({ emails }) });
      setEnv(d);
      setLoginsText(d.test_login_emails.join("\n"));
      push({ title: "Test sign-in saved", description: d.test_login_emails.length ? `${d.test_login_emails.length} account(s) can sign in` : "Only admin accounts can sign in" });
    } catch (err) {
      push({ title: "That didn't work", description: err instanceof Error ? err.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  const test = env?.effective === "test";

  return (
    <div>
      <PageHeader
        title="Test mode"
        description="Let the testing team try everything (signing up, ordering, admin work) on a copy of the live data, then throw the copy away."
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}

      <Panel>
        <PanelHeader
          title="The shop is using"
          actions={env && <Pill tone={test ? "warning" : "success"}>{test ? "Test data" : "Live data"}</Pill>}
          description={env?.changed_at ? `Last switched ${timeAgo(env.changed_at)}${env.changed_by_email ? ` by ${env.changed_by_email}` : ""}.` : undefined}
        />
        <PanelBody className="space-y-4">
          {!env ? (
            <div className="skeleton h-24" />
          ) : (
            <>
              {env.mode === "test" && !env.test_exists && (
                <Alert tone="danger">Test mode is selected but the test data is missing, so the shop is on live data. Switch to test again to make a new copy.</Alert>
              )}
              {env.out_of_date && (
                <Alert tone="info">The test data was copied before the latest update to the shop and may be missing new fields. Copy the live data again.</Alert>
              )}
              <dl className="grid grid-cols-[minmax(0,1fr)] gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-muted">Test data</dt>
                  <dd className="font-medium">{env.test_exists ? `Copied ${env.test_synced_at ? dateTime(env.test_synced_at) : ""}` : "None"}</dd>
                </div>
                <div>
                  <dt className="text-muted">Size of the copy</dt>
                  <dd className="num font-medium">{env.test_exists ? size(env.test_size_bytes) : "—"}</dd>
                </div>
                <div>
                  <dt className="text-muted">Card payments in test mode</dt>
                  <dd className="font-medium">{env.stripe_test_configured ? "Stripe test cards (no charges)" : "Test payment only (no Stripe test keys set)"}</dd>
                </div>
              </dl>
              <div className="flex flex-wrap gap-2 border-t border-line pt-4">
                {test ? (
                  <>
                    <Button size="sm" disabled={busy} onClick={() => setConfirm("live")}>
                      Switch to live
                    </Button>
                    <Button size="sm" variant="secondary" disabled={busy} onClick={() => setConfirm("sync")}>
                      Copy live data again
                    </Button>
                  </>
                ) : (
                  <>
                    <Button size="sm" disabled={busy} onClick={() => setConfirm("test")}>
                      Switch to test
                    </Button>
                    {env.test_exists && (
                      <Button size="sm" variant="ghost" className="text-danger" disabled={busy} onClick={() => setConfirm("delete")}>
                        Delete test data
                      </Button>
                    )}
                  </>
                )}
              </div>
              <p className="text-xs text-muted">Switching to test always starts from a fresh copy of the live data. Copying takes a few seconds for a shop this size.</p>
            </>
          )}
        </PanelBody>
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Test inbox" description="The copy holds real customers' email addresses. In test mode every email (order confirmations, reminders, campaigns) goes here instead." />
          <PanelBody>
            <form onSubmit={saveMailTo} className="flex flex-wrap gap-2">
              <label htmlFor="test-mail-to" className="sr-only">
                Test inbox email address
              </label>
              <Input id="test-mail-to" type="email" value={mailTo} onChange={(e) => setMailTo(e.target.value)} placeholder="qa@windycitywares.com" className="h-9 min-w-0 flex-1" />
              <Button type="submit" size="sm" variant="secondary" disabled={busy}>
                Save inbox
              </Button>
            </form>
            <p className="mt-2 text-xs text-muted">Leave empty to send no emails at all while testing.</p>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Test sign-in" description="The copy holds real customers' password hashes, so in test mode only these accounts can sign in." />
          <PanelBody>
            <form onSubmit={saveLogins} className="grid gap-2">
              <label htmlFor="test-logins" className="text-sm font-medium">
                Accounts that can sign in
              </label>
              <textarea
                id="test-logins"
                rows={4}
                value={loginsText}
                onChange={(e) => setLoginsText(e.target.value)}
                placeholder={"qa@windycitywares.com\ncustomer@windycitywares.com"}
                className="min-h-24 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
              />
              <div>
                <Button type="submit" size="sm" variant="secondary" disabled={busy}>
                  Save sign-in list
                </Button>
              </div>
            </form>
            <p className="mt-2 text-xs text-muted">One email per line. Leave empty to allow only admin accounts. Accounts that are not listed cannot sign in while test mode is on.</p>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="While test mode is on" />
          <PanelBody>
            <ul className="list-disc space-y-1.5 pl-5 text-sm">
              <li>Every page shows a &ldquo;Test mode&rdquo; banner.</li>
              <li>No card is charged: Stripe test cards or the no-charge test payment.</li>
              <li>No email reaches a customer.</li>
              <li>New ids and order numbers start 1,000,000 above live, so test records stand out.</li>
              <li>Testers sign up and use the shop like customers; staff accounts work with their usual passwords.</li>
              <li>Real shoppers visiting meanwhile also see the copy, so test before launch or at quiet times.</li>
            </ul>
          </PanelBody>
        </Panel>
      </div>

      {confirm && (
        <ConfirmDialog
          open
          title={CONFIRM[confirm].title}
          message={CONFIRM[confirm].message}
          confirmLabel={busy ? "Working…" : CONFIRM[confirm].label}
          tone={CONFIRM[confirm].tone}
          busy={busy}
          onConfirm={() => run(confirm)}
          onCancel={() => setConfirm(null)}
        />
      )}

      <Modal
        open={switched !== null}
        onClose={() => {
          logout();
          router.replace("/login?next=/admin/environment");
        }}
        title={switched === "test" ? "The shop is now in test mode" : "The shop is back on live data"}
        description="Everyone has been signed out. Sign in again with your usual password."
      >
        <Button
          onClick={() => {
            logout();
            router.replace("/login?next=/admin/environment");
          }}
        >
          Sign in again
        </Button>
      </Modal>
    </div>
  );
}
