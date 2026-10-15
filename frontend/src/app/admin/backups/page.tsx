"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { dateTime, timeAgo } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";
import { RestoreDialog, backupDate } from "@/components/admin/RestoreDialog";

interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: "running" | "success" | "failed";
  trigger: "schedule" | "manual";
  actor_email: string | null;
  file_name: string | null;
  size_bytes: number | null;
  error: string | null;
}
interface Backups {
  enabled: boolean;
  hour: number;
  keep: number;
  repo: string | null;
  branch: string;
  updated_at: string | null;
  updated_by_email: string | null;
  secrets: { token: boolean; passphrase: boolean; pg_dump: boolean };
  runs: Run[];
  files: { name: string; size: number | null }[] | null;
  files_error: string | null;
}

const STATUS: Record<Run["status"], { label: string; tone: Tone }> = {
  success: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  running: { label: "Running", tone: "info" },
};
const mb = (n: number | null) => (n == null ? "—" : n < 1e6 ? `${Math.max(1, Math.round(n / 1e3))} KB` : `${(n / 1e6).toFixed(1)} MB`);
const hourLabel = (h: number) => new Date(2000, 0, 1, h).toLocaleTimeString("en-US", { hour: "numeric" });

/** Daily encrypted database backups to a private GitHub repository (admins only). See docs/DEPLOYMENT.md → Backups. */
export default function AdminBackups() {
  const { push } = useToast();
  const [data, setData] = useState<Backups | null>(null);
  const [form, setForm] = useState({ enabled: false, hour: 3, keep: 5, repo: "", branch: "main" });
  const [busy, setBusy] = useState<"" | "save" | "run">("");
  const [restoring, setRestoring] = useState<string | null>(null);
  const [error, setError] = useState("");

  const show = useCallback((d: Backups) => {
    setData(d);
    setForm({ enabled: d.enabled, hour: d.hour, keep: d.keep, repo: d.repo ?? "", branch: d.branch });
  }, []);
  const load = useCallback(() => {
    apiFetch<Backups>("/admin/backups").then(
      (d) => {
        show(d);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [show]);
  useEffect(load, [load]);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // Read what is in the boxes right now (a browser's autofill can show text the page never received).
    const fields = new FormData(e.currentTarget);
    const repo = String(fields.get("repo") ?? "")
      .trim()
      .replace(/^https?:\/\/github\.com\//i, "")
      .replace(/\.git$/i, "")
      .replace(/\/+$/, "");
    const next = {
      enabled: fields.get("enabled") === "on",
      hour: Number(fields.get("hour") ?? form.hour),
      keep: Number(fields.get("keep") ?? form.keep),
      repo,
      branch: String(fields.get("branch") ?? "").trim() || "main",
    };
    setForm(next);
    if (next.enabled && !repo) {
      push({ title: "Not saved", description: "Type the repository in the box first, e.g. windycitywares/wcw-backups.", tone: "danger" });
      return;
    }
    setBusy("save");
    try {
      show(await apiFetch<Backups>("/admin/backups", { method: "PUT", body: JSON.stringify({ ...next, repo: repo || null }) }));
      push({ title: "Backup settings saved", description: next.enabled ? `${repo}: daily after ${hourLabel(next.hour)}, keeping ${next.keep}` : `${repo || "No repository"}: automatic backups are off` });
    } catch (err) {
      push({ title: "Not saved", description: err instanceof Error ? err.message : undefined, tone: "danger" });
    } finally {
      setBusy("");
    }
  }

  async function runNow() {
    setBusy("run");
    try {
      const r = await apiFetch<{ status: "success" | "failed"; file_name: string; size_bytes: number | null; error: string | null }>("/admin/backups/run", { method: "POST" });
      if (r.status === "success") push({ title: "Backed up", description: `${r.file_name} (${mb(r.size_bytes)})` });
      else push({ title: "Backup failed", description: r.error ?? undefined, tone: "danger" });
      load();
    } catch (err) {
      push({ title: "Backup failed", description: err instanceof Error ? err.message : undefined, tone: "danger" });
    } finally {
      setBusy("");
    }
  }

  const s = data?.secrets;
  const missing = s ? [!s.token && "BACKUP_GITHUB_TOKEN", !s.passphrase && "BACKUP_PASSPHRASE", !s.pg_dump && "pg_dump (BACKUP_PG_DUMP)"].filter(Boolean) : [];
  const last = data?.runs.find((r) => r.status === "success");
  const columns: Column<Run>[] = [
    { key: "when", header: "When", cell: (r) => <span className="whitespace-nowrap text-sm">{dateTime(r.started_at)}</span> },
    { key: "status", header: "Result", cell: (r) => <Pill tone={STATUS[r.status].tone}>{STATUS[r.status].label}</Pill> },
    {
      key: "what",
      header: "Details",
      cell: (r) => (
        <span className="block max-w-[26rem] text-sm">
          {r.status === "failed" ? <span className="text-danger">{r.error}</span> : <span className="font-mono text-xs">{r.file_name}</span>}
          <span className="block text-xs text-muted">{r.trigger === "manual" ? `By ${r.actor_email ?? "staff"}` : "Daily schedule"}</span>
        </span>
      ),
    },
    { key: "size", header: "Size", align: "right", hide: "md", cell: (r) => <span className="num text-sm">{mb(r.size_bytes)}</span> },
  ];

  return (
    <div>
      <PageHeader
        title="Backups"
        description="A daily encrypted copy of the live database, kept in a private GitHub repository. Only the newest few are kept."
        actions={
          <span className="flex flex-col items-end gap-1">
            <Button size="sm" disabled={!!busy || !data?.repo || missing.length > 0} onClick={runNow}>
              {busy === "run" ? "Backing up…" : "Back up now"}
            </Button>
            {data && (!data.repo || missing.length > 0) && (
              <span className="text-xs text-muted">{missing.length > 0 ? "Available once the server is set up" : "Save a repository first"}</span>
            )}
          </span>
        }
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      {missing.length > 0 && (
        <Alert tone="danger" className="mb-4">
          Not set up on the server yet: {missing.join(", ")}. Add them to backend/.env (see docs/DEPLOYMENT.md → Backups).
        </Alert>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Settings" description={data?.updated_by_email && data.updated_at ? `Changed ${timeAgo(data.updated_at)} by ${data.updated_by_email}.` : undefined} />
          <PanelBody>
            <form onSubmit={save} className="space-y-4">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input type="checkbox" name="enabled" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} className="size-4 accent-[var(--color-accent)]" />
                Back up automatically every day
              </label>
              <Field label="Private GitHub repository" hint="owner/name, e.g. windycitywares/wcw-backups. Public repositories are refused.">
                {(p) => (
                  <Input
                    {...p}
                    name="repo"
                    autoComplete="off"
                    spellCheck={false}
                    value={form.repo}
                    onChange={(e) => setForm({ ...form, repo: e.target.value })}
                    placeholder="windycitywares/wcw-backups"
                  />
                )}
              </Field>
              <div className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-3">
                <Field label="Time (shop time)">
                  {(p) => (
                    <Select {...p} name="hour" value={form.hour} onChange={(e) => setForm({ ...form, hour: Number(e.target.value) })}>
                      {Array.from({ length: 24 }, (_, h) => (
                        <option key={h} value={h}>
                          After {hourLabel(h)}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label="Backups to keep">
                  {(p) => <Input {...p} name="keep" type="number" min={1} max={30} value={form.keep} onChange={(e) => setForm({ ...form, keep: Number(e.target.value) })} />}
                </Field>
                <Field label="Branch">{(p) => <Input {...p} name="branch" autoComplete="off" value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })} />}</Field>
              </div>
              <Button type="submit" size="sm" variant="secondary" disabled={!!busy}>
                {busy === "save" ? "Saving…" : "Save settings"}
              </Button>
            </form>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="In the repository" description={last ? `Last backup ${timeAgo(last.started_at)}.` : "No backup yet."} />
          <PanelBody>
            {!data ? (
              <div className="skeleton h-24" />
            ) : !data.repo ? (
              <p className="text-sm text-muted">Choose a repository to see the backups in it.</p>
            ) : data.files_error ? (
              <Alert tone="danger">{data.files_error}</Alert>
            ) : (data.files ?? []).length === 0 ? (
              <p className="text-sm text-muted">No backups in {data.repo} yet.</p>
            ) : (
              <ul className="divide-y divide-line text-sm">
                {(data.files ?? []).map((f) => (
                  <li key={f.name} className="flex items-center justify-between gap-3 py-2">
                    <span className="min-w-0">
                      <span className="block font-medium">{backupDate(f.name)}</span>
                      <span className="block truncate font-mono text-xs text-muted">
                        {f.name} · {mb(f.size)}
                      </span>
                    </span>
                    <Button size="sm" variant="secondary" disabled={!!busy || missing.length > 0} onClick={() => setRestoring(f.name)}>
                      Restore
                      <span className="sr-only"> backup from {backupDate(f.name)}</span>
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-4 text-xs text-muted">
              Files are encrypted: they can only be opened with the backup passphrase from the server&apos;s settings. Keep a copy of it in your password manager. Restoring is
              described in docs/DEPLOYMENT.md → Backups.
            </p>
          </PanelBody>
        </Panel>
      </div>

      <RestoreDialog file={restoring} onClose={() => setRestoring(null)} onDone={load} />

      <Panel className="mt-6">
        <PanelHeader title="History" description="The last 20 attempts." />
        <DataTable columns={columns} rows={data?.runs ?? null} rowKey={(r) => r.id} caption="Backup history" empty="No backups have run yet." />
      </Panel>
    </div>
  );
}
