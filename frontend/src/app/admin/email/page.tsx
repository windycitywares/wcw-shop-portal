"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Email {
  from_name: string | null;
  from_address: string | null;
  reply_to: string | null;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_security: "ssl" | "starttls" | "none" | null;
  smtp_user: string | null;
}
interface Form {
  from_name: string;
  from_address: string;
  reply_to: string;
  smtp_host: string;
  smtp_port: string;
  smtp_security: string;
  smtp_user: string;
  smtp_password: string;
}
type Status = Record<string, boolean>;

const PORT_FOR: Record<string, number> = { ssl: 465, starttls: 587, none: 25 };

const toForm = (e: Email): Form => ({
  from_name: e.from_name ?? "",
  from_address: e.from_address ?? "",
  reply_to: e.reply_to ?? "",
  smtp_host: e.smtp_host ?? "",
  smtp_port: e.smtp_port == null ? "" : String(e.smtp_port),
  smtp_security: e.smtp_security ?? "",
  smtp_user: e.smtp_user ?? "",
  smtp_password: "",
});

export default function AdminEmailSending() {
  const { user } = useAuth();
  const { push } = useToast();
  const [form, setForm] = useState<Form | null>(null);
  const [status, setStatus] = useState<Status>({});
  const [clearPassword, setClearPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);

  useEffect(() => {
    apiFetch<{ settings: { email: Email }; status: Status }>("/admin/settings").then(
      (r) => {
        setForm(toForm(r.settings.email));
        setStatus(r.status);
      },
      (e) => setError(e.message),
    );
  }, []);
  useEffect(() => setTestTo((old) => old || user?.email || ""), [user?.email]);

  if (!form) {
    return (
      <div>
        <PageHeader title="Email sending" description="Loading…" />
        {error && <Alert tone="danger">{error}</Alert>}
      </div>
    );
  }
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setError("");
    try {
      const patch: Record<string, unknown> = {
        from_name: form.from_name,
        from_address: form.from_address,
        reply_to: form.reply_to,
        smtp_host: form.smtp_host,
        smtp_port: form.smtp_port === "" ? null : Number(form.smtp_port),
        smtp_security: form.smtp_security || null,
        smtp_user: form.smtp_user,
      };
      if (form.smtp_password) patch.smtp_password = form.smtp_password;
      if (clearPassword) patch.clear_smtp_password = true;
      const res = await apiFetch<{ settings: { email: Email }; status: Status }>("/admin/settings/email", { method: "PUT", body: JSON.stringify(patch) });
      setForm(toForm(res.settings.email));
      setStatus(res.status);
      setClearPassword(false);
      push({ title: "Email settings saved", description: res.status.email_configured ? "Outgoing email is on." : "No mail server is set, so nothing is sent." });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save");
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await apiFetch<{ detail: string }>("/admin/settings/test-email", { method: "POST", body: JSON.stringify({ to: testTo }) });
      setTestResult({ ok: true, detail: r.detail });
    } catch (err) {
      setTestResult({ ok: false, detail: err instanceof Error ? err.message : "Couldn't send" });
    } finally {
      setTesting(false);
    }
  }

  const passwordSet = !!status.email_password_set && !clearPassword;
  return (
    <div>
      <PageHeader
        title="Email sending"
        description="Who the shop's emails come from and which mail server sends them: welcome, password-reset, order and newsletter emails. Leave a box empty to use the server's own setup."
        actions={
          <div className="flex items-center gap-4">
            {status.email_configured ? <Pill tone="success">On</Pill> : <Pill tone="warning">No mail server</Pill>}
            <Link href="/admin/email-templates" className="text-sm font-medium text-accent underline">
              Edit email wording
            </Link>
          </div>
        }
      />
      <form onSubmit={save} className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
        {error && (
          <Alert tone="danger" className="xl:col-span-2">
            {error}
          </Alert>
        )}
        <Panel>
          <PanelHeader title="Mail server (SMTP)" description="From your hosting's Email Accounts → Connect Devices page. When a host is set here, its login replaces the server's." />
          <PanelBody className="grid gap-4 sm:grid-cols-2">
            <Field label="SMTP host" className="sm:col-span-2" hint="e.g. mail.windycitywares.com. Empty: use the server's setup.">
              {(p) => <Input {...p} value={form.smtp_host} onChange={(e) => set("smtp_host", e.target.value)} autoComplete="off" />}
            </Field>
            <Field label="Security">
              {(p) => (
                <Select
                  {...p}
                  value={form.smtp_security}
                  onChange={(e) => setForm({ ...form, smtp_security: e.target.value, smtp_port: e.target.value ? String(PORT_FOR[e.target.value]) : form.smtp_port })}
                >
                  <option value="">Choose…</option>
                  <option value="ssl">SSL/TLS (port 465)</option>
                  <option value="starttls">STARTTLS (port 587)</option>
                  <option value="none">None (not recommended)</option>
                </Select>
              )}
            </Field>
            <Field label="Port">
              {(p) => <Input {...p} type="number" min={1} max={65535} value={form.smtp_port} onChange={(e) => set("smtp_port", e.target.value)} />}
            </Field>
            <Field label="Username" hint="Usually the full mailbox address.">
              {(p) => <Input {...p} value={form.smtp_user} onChange={(e) => set("smtp_user", e.target.value)} autoComplete="off" />}
            </Field>
            <Field label="Password" hint={passwordSet ? "Saved and encrypted. Leave blank to keep it." : "Stored encrypted; never shown again."}>
              {(p) => (
                <Input
                  {...p}
                  type="password"
                  value={form.smtp_password}
                  onChange={(e) => set("smtp_password", e.target.value)}
                  autoComplete="new-password"
                  placeholder={passwordSet ? "••••••••" : ""}
                />
              )}
            </Field>
            {status.email_password_set && (
              <label className="flex items-center gap-2 text-sm sm:col-span-2">
                <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={clearPassword} onChange={(e) => setClearPassword(e.target.checked)} />
                Remove the saved password
              </label>
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Sender" description="What customers see in their inbox." />
          <PanelBody className="grid gap-4 sm:grid-cols-2">
            <Field label="From name" hint="e.g. Windy City Wares">
              {(p) => <Input {...p} value={form.from_name} onChange={(e) => set("from_name", e.target.value)} />}
            </Field>
            <Field label="From address" hint="Must be allowed by your mail server.">
              {(p) => <Input {...p} type="email" value={form.from_address} onChange={(e) => set("from_address", e.target.value)} />}
            </Field>
            <Field label="Reply-to address" hint="Optional. Where replies go (default: the from address)." className="sm:col-span-2">
              {(p) => <Input {...p} type="email" value={form.reply_to} onChange={(e) => set("reply_to", e.target.value)} />}
            </Field>
          </PanelBody>
        </Panel>

        <div className="flex flex-wrap items-center gap-4 xl:col-span-2">
          <Button type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save email settings"}
          </Button>
        </div>
      </form>

      <Panel className="mt-6">
        <PanelHeader title="Send a test email" description="Uses the saved settings (save first). Shows the mail server's answer if it fails." />
        <PanelBody className="flex flex-wrap items-end gap-3">
          <Field label="Send to" className="min-w-0 flex-1 sm:max-w-sm">
            {(p) => <Input {...p} type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)} />}
          </Field>
          <Button variant="secondary" onClick={() => void test()} disabled={testing || !testTo}>
            {testing ? "Sending…" : "Send test email"}
          </Button>
          {testResult && (
            <p role="status" className={`w-full text-sm ${testResult.ok ? "text-success" : "text-danger"}`}>
              {testResult.detail}
            </p>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
