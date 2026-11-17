"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { dateTime } from "@/components/admin/charts/format";
import { ConfirmDialog } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Connection {
  client_id: string | null;
  secret_set: boolean;
  connected: boolean;
  shop_name: string | null;
  connected_at: string | null;
  listings_synced_at: string | null;
  orders_synced_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
  redirect_uri: string;
}

const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 gap-y-0.5 py-2.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  );
}

function EtsyPage() {
  const { can } = useAuth();
  const { push } = useToast();
  const params = useSearchParams();
  const [conn, setConn] = useState<Connection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [clientId, setClientId] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const admin = can("etsy:settings");

  const load = useCallback(async () => {
    try {
      const c = await apiFetch<Connection>("/admin/etsy/connection");
      setConn(c);
      setClientId((prev) => prev || c.client_id || "");
    } catch (e) {
      setError(errorText(e));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const outcome = params.get("etsy");
  const saveCredentials = async () => {
    setBusy(true);
    try {
      const c = await apiFetch<Connection>("/admin/etsy/credentials", {
        method: "PUT",
        body: JSON.stringify({ client_id: clientId.trim() || null, client_secret: secret || null }),
      });
      setConn(c);
      setSecret("");
      push({ tone: "success", title: "Etsy keys saved" });
    } catch (e) {
      push({ tone: "danger", title: errorText(e) });
    } finally {
      setBusy(false);
    }
  };
  const connect = async () => {
    setBusy(true);
    try {
      const r = await apiFetch<{ url: string }>("/admin/etsy/connect", { method: "POST" });
      window.location.href = r.url;
    } catch (e) {
      push({ tone: "danger", title: errorText(e) });
      setBusy(false);
    }
  };
  const disconnect = async () => {
    setBusy(true);
    try {
      setConn(await apiFetch<Connection>("/admin/etsy/disconnect", { method: "POST" }));
      push({ tone: "success", title: "Etsy disconnected" });
    } catch (e) {
      push({ tone: "danger", title: errorText(e) });
    } finally {
      setBusy(false);
      setConfirmDisconnect(false);
    }
  };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader title="Etsy" description="Your Etsy sales and listings, read from Etsy. Etsy stays the source of truth; costs, tracking and notes are added here." />
      {outcome === "connected" ? <Alert tone="success">Etsy is connected{params.get("shop") ? `: ${params.get("shop")}` : ""}.</Alert> : null}
      {outcome === "failed" ? <Alert tone="danger">Etsy was not connected. {params.get("reason")}</Alert> : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <Panel>
        <PanelHeader title="Connection" />
        <PanelBody>
          {!conn ? (
            <div className="skeleton h-32" />
          ) : (
            <>
              <dl className="divide-y divide-line">
                <Row label="Status">
                  {conn.connected ? <Pill tone="success">Connected</Pill> : <Pill tone="warning">Not connected</Pill>}
                </Row>
                {conn.connected ? <Row label="Shop">{conn.shop_name}</Row> : null}
                {conn.connected_at ? <Row label="Connected">{dateTime(conn.connected_at)}</Row> : null}
                {conn.last_error ? <Row label="Last problem"><span className="text-danger">{conn.last_error}</span></Row> : null}
              </dl>
              {admin ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button onClick={connect} disabled={busy || !conn.client_id || !conn.secret_set}>
                    {conn.connected ? "Reconnect Etsy" : "Connect Etsy"}
                  </Button>
                  {conn.connected ? (
                    <Button variant="secondary" onClick={() => setConfirmDisconnect(true)} disabled={busy}>
                      Disconnect Etsy
                    </Button>
                  ) : null}
                </div>
              ) : (
                <p className="mt-3 text-sm text-muted">Only an admin can connect or reconnect Etsy.</p>
              )}
            </>
          )}
        </PanelBody>
      </Panel>

      {admin && conn ? (
        <Panel>
          <PanelHeader title="Etsy app keys" />
          <PanelBody className="grid grid-cols-[minmax(0,1fr)] gap-4">
            <p className="text-sm text-muted">
              Copy these from your app on Etsy&apos;s developer page. The shared secret is stored encrypted and is never shown again.
            </p>
            <Field label="Keystring">{(p) => <Input {...p} value={clientId} onChange={(e) => setClientId(e.target.value)} autoComplete="off" spellCheck={false} />}</Field>
            <Field label="Shared secret" hint={conn.secret_set ? "Saved. Type a new one only to replace it." : undefined}>
              {(p) => <Input {...p} type="password" value={secret} onChange={(e) => setSecret(e.target.value)} autoComplete="new-password" />}
            </Field>
            <div>
              <Button onClick={saveCredentials} disabled={busy || !clientId.trim()}>Save Etsy keys</Button>
            </div>
            <p className="text-sm text-muted">
              Redirect URI on your Etsy app must be exactly: <code className="break-all">{conn.redirect_uri}</code>
            </p>
          </PanelBody>
        </Panel>
      ) : null}

      <ConfirmDialog
        open={confirmDisconnect}
        title="Disconnect Etsy?"
        message="Syncing stops until you connect again. Orders and listings already imported stay."
        confirmLabel="Disconnect Etsy"
        busy={busy}
        onConfirm={disconnect}
        onCancel={() => setConfirmDisconnect(false)}
      />
    </div>
  );
}

export default function AdminEtsy() {
  return (
    <Suspense fallback={<div className="skeleton h-64" />}>
      <EtsyPage />
    </Suspense>
  );
}
