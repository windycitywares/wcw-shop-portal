"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { dateTime, timeAgo } from "@/components/admin/charts/format";
import { Icon } from "@/components/admin/ui/Icon";
import { ConfirmDialog } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

type Mode = "auto" | "schedule" | "paused";
interface Version {
  commit: string | null;
  subject: string | null;
  date: string | null;
}
interface Release {
  id: number;
  commit: string;
  pr_number: number | null;
  title: string;
  details: string | null;
  committed_at: string | null;
  deployed_at: string;
  storefront_build: string | null;
  main_site_build: string | null;
  current: boolean;
}
interface DeployStatus {
  mode: Mode;
  interval_minutes: number;
  schedule_times: string[];
  timezone: string;
  requested_at: string | null;
  requested_by: string | null;
  last_check_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  running: boolean;
  last_reason: string | null;
  last_result: string | null;
  updated_at: string | null;
  updated_by: string | null;
  api: Version;
  storefront_build: string | null;
  main_site_build: string | null;
  cron_seen: boolean;
  last_seen_at: string | null;
}

const MODE_LABEL: Record<Mode, string> = { auto: "Automatic", schedule: "At set times", paused: "Paused" };
const MODE_HELP: Record<Mode, string> = {
  auto: "Check GitHub regularly and install anything new.",
  schedule: "Only install updates at the times below, e.g. overnight.",
  paused: "Never install on its own. “Deploy now” still works.",
};
const INTERVALS = [1, 5, 10, 15, 30, 60, 120, 240];
const errorText = (e: unknown) => (e instanceof Error ? e.message : undefined);

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 gap-y-0.5 py-2.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  );
}

const Build = ({ id }: { id: string | null }) => (id ? <span className="font-mono">{id.slice(0, 7)}</span> : <span className="text-muted">—</span>);

/** Admin → Deployments: when merged changes go live, "Deploy now", what's live and the server's deploy log. */
export default function AdminDeployments() {
  const { push } = useToast();
  const [status, setStatus] = useState<DeployStatus | null>(null);
  const [log, setLog] = useState("");
  const [releases, setReleases] = useState<Release[]>([]);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<Mode>("auto");
  const [interval, setIntervalMinutes] = useState(10);
  const [times, setTimes] = useState<string[]>([]);
  const [newTime, setNewTime] = useState("02:00");
  const [busy, setBusy] = useState(false);
  const [confirmPause, setConfirmPause] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  const refresh = useCallback(async (withForm = false) => {
    try {
      const [s, l, r] = await Promise.all([
        apiFetch<DeployStatus>("/admin/deploy"),
        apiFetch<{ log: string }>("/admin/deploy/log?lines=200"),
        apiFetch<{ releases: Release[] }>("/admin/deploy/releases"),
      ]);
      setStatus(s);
      setLog(l.log);
      setReleases(r.releases);
      setError("");
      if (withForm) {
        setMode(s.mode);
        setIntervalMinutes(s.interval_minutes);
        setTimes(s.schedule_times);
      }
    } catch (e) {
      setError(errorText(e) ?? "Couldn't load deployments");
    }
  }, []);

  useEffect(() => {
    void refresh(true);
  }, [refresh]);

  // While a deploy is queued or running, refresh every 5 seconds so the page shows progress without a reload.
  const active = !!status && (status.running || !!status.requested_at);
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(t);
  }, [active, refresh]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log]);

  async function act(fn: () => Promise<DeployStatus>, title: string, description?: string) {
    setBusy(true);
    try {
      setStatus(await fn());
      push({ title, description });
    } catch (e) {
      push({ title: "Not saved", description: errorText(e), tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  const deployNow = () =>
    act(() => apiFetch<DeployStatus>("/admin/deploy/now", { method: "POST" }), "Deploy queued", "It starts within a minute; the log below follows it.");
  const cancel = () => act(() => apiFetch<DeployStatus>("/admin/deploy/now", { method: "DELETE" }), "Deploy cancelled");
  const save = () =>
    act(
      () => apiFetch<DeployStatus>("/admin/deploy/config", { method: "PUT", body: JSON.stringify({ mode, interval_minutes: interval, schedule_times: times }) }),
      "Update settings saved",
      mode === "auto" ? `Automatic, every ${interval} min` : mode === "schedule" ? `At ${times.join(", ")}` : "Paused: nothing installs on its own",
    );

  if (!status) {
    return (
      <div>
        <PageHeader title="Deployments" description="When merged changes go live on the shop." />
        {error ? <Alert tone="danger">{error}</Alert> : <div className="skeleton h-40" />}
      </div>
    );
  }

  const changed = mode !== status.mode || interval !== status.interval_minutes || times.join() !== status.schedule_times.join();
  const state = status.running ? (
    <Pill tone="info">Deploying…</Pill>
  ) : status.requested_at ? (
    <Pill tone="accent">Queued</Pill>
  ) : status.mode === "paused" ? (
    <Pill tone="warning">Paused</Pill>
  ) : (
    <Pill tone="success">{MODE_LABEL[status.mode]}</Pill>
  );

  return (
    <div>
      <PageHeader
        title="Deployments"
        description="Changes merged on GitHub go live here: storefront, API and windycitywares.com. Deploy now, pause, or choose when."
        actions={
          <span className="flex flex-wrap items-center gap-2">
            {state}
            {status.requested_at ? (
              <Button size="sm" variant="secondary" disabled={busy || status.running} onClick={() => void cancel()}>
                Cancel deploy
              </Button>
            ) : (
              <Button size="sm" disabled={busy || status.running} onClick={() => void deployNow()}>
                <Icon name="download" className="size-4" />
                Deploy now
              </Button>
            )}
          </span>
        }
      />

      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      {!status.cron_seen && (
        <Alert tone="info" className="mb-4">
          The server hasn&apos;t checked in for a few minutes{status.last_seen_at ? ` (last ${timeAgo(status.last_seen_at)})` : ""}. Set the cron job in cPanel to run
          every minute (docs/DEPLOYMENT.md → Updating); until then “Deploy now” waits for its next run.
        </Alert>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="What's live" />
          <PanelBody>
            <dl className="divide-y divide-line">
              <Row label="API">
                {status.api.commit ? (
                  <>
                    <span className="font-mono">{status.api.commit}</span> {status.api.subject}
                    {status.api.date && <span className="block text-xs text-muted">{dateTime(status.api.date)}</span>}
                  </>
                ) : (
                  <span className="text-muted">—</span>
                )}
              </Row>
              <Row label="Storefront build">
                <Build id={status.storefront_build} />
              </Row>
              <Row label="windycitywares.com build">
                <Build id={status.main_site_build} />
              </Row>
              <Row label="Last check for updates">
                {status.last_check_at ? `${timeAgo(status.last_check_at)}${status.last_reason ? ` (${status.last_reason})` : ""}` : "Never"}
              </Row>
              <Row label="Last result">{status.last_result ?? "—"}</Row>
              {status.requested_at && (
                <Row label="Queued">
                  {timeAgo(status.requested_at)}
                  {status.requested_by ? ` by ${status.requested_by}` : ""}
                </Row>
              )}
            </dl>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader
            title="When to update"
            description={`Times are store time (${status.timezone}).${status.updated_by && status.updated_at ? ` Changed ${timeAgo(status.updated_at)} by ${status.updated_by}.` : ""}`}
          />
          <PanelBody className="grid gap-4">
            <fieldset className="grid gap-2 text-sm">
              <legend className="mb-1 font-medium">Updates</legend>
              {(["auto", "schedule", "paused"] as Mode[]).map((m) => (
                <label key={m} className="flex items-start gap-3">
                  <input type="radio" name="mode" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={mode === m} onChange={() => setMode(m)} />
                  <span>
                    <span className="font-medium">{MODE_LABEL[m]}</span>
                    <span className="block text-muted">{MODE_HELP[m]}</span>
                  </span>
                </label>
              ))}
            </fieldset>
            {mode === "auto" && (
              <Field label="Check every (minutes)" className="max-w-40">
                {(p) => (
                  <Select {...p} value={interval} onChange={(e) => setIntervalMinutes(Number(e.target.value))}>
                    {INTERVALS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            {mode === "schedule" && (
              <div className="grid gap-2">
                <div className="flex flex-wrap items-end gap-2">
                  <Field label="Add a time">{(p) => <Input {...p} type="time" value={newTime} onChange={(e) => setNewTime(e.target.value)} />}</Field>
                  <Button size="sm" variant="secondary" disabled={!newTime || times.includes(newTime)} onClick={() => setTimes([...times, newTime].sort())}>
                    <Icon name="plus" className="size-4" />
                    Add time
                  </Button>
                </div>
                <ul className="flex flex-wrap gap-2" aria-label="Update times">
                  {times.map((t) => (
                    <li key={t} className="inline-flex items-center gap-1 rounded-full bg-sand py-0.5 pl-3 pr-1 text-sm">
                      {t}
                      <button type="button" onClick={() => setTimes(times.filter((x) => x !== t))} className="grid size-6 place-items-center rounded-full hover:bg-line">
                        <Icon name="close" className="size-3.5" />
                        <span className="sr-only">Remove {t}</span>
                      </button>
                    </li>
                  ))}
                  {times.length === 0 && <li className="text-sm text-muted">No times yet.</li>}
                </ul>
              </div>
            )}
            <div>
              <Button
                size="sm"
                disabled={busy || !changed || (mode === "schedule" && times.length === 0)}
                onClick={() => (mode === "paused" && status.mode !== "paused" ? setConfirmPause(true) : void save())}
              >
                Save update settings
              </Button>
            </div>
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader title="Recent versions" description="The last five versions that went live, each described by the pull request behind it." />
        <PanelBody>
          {releases.length === 0 ? (
            <p className="text-sm text-muted">No versions recorded yet.</p>
          ) : (
            <ol className="divide-y divide-line" aria-label="Recent versions">
              {releases.map((r) => (
                <li key={r.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                      {r.current ? <Pill tone="success">Latest · live now</Pill> : <Pill tone="neutral">Earlier</Pill>}
                      <span className="min-w-0 break-words">{r.title}</span>
                    </p>
                    {r.details && <p className="mt-1 whitespace-pre-line break-words text-sm text-muted">{r.details}</p>}
                    <p className="mt-1 text-xs text-muted">
                      {r.pr_number ? `PR #${r.pr_number} · ` : ""}
                      <span className="font-mono">{r.commit}</span> · live {dateTime(r.deployed_at)}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </PanelBody>
      </Panel>

      <Panel className="mt-6">
        <PanelHeader
          title="Deploy log"
          description="The latest lines from the server (~/logs/wcw-deploy.log)."
          actions={
            <Button size="sm" variant="ghost" onClick={() => void refresh()}>
              Refresh
            </Button>
          }
        />
        <pre
          ref={logRef}
          tabIndex={0}
          aria-label="Deploy log"
          className="max-h-[28rem] overflow-auto whitespace-pre-wrap break-words bg-night px-5 py-4 font-mono text-xs leading-relaxed text-night-muted"
        >
          {log || "No log yet."}
        </pre>
      </Panel>

      <ConfirmDialog
        open={confirmPause}
        title="Pause updates?"
        tone="primary"
        confirmLabel="Pause updates"
        busy={busy}
        onCancel={() => setConfirmPause(false)}
        onConfirm={() => {
          setConfirmPause(false);
          void save();
        }}
        message="Merged changes won't go live on their own until you switch back to Automatic or At set times. “Deploy now” still installs them whenever you click it."
      />
    </div>
  );
}
