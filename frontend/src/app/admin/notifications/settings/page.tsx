"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { Channels, LiveCategory, NotificationPrefs, SoundName } from "@/lib/liveCategories";
import { useLiveStatus } from "@/components/admin/live/LiveProvider";
import { SOUND_LABELS, playSound } from "@/components/admin/live/sounds";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

type Loaded = { prefs: NotificationPrefs; categories: Record<LiveCategory, string> };
const CHANNELS: { key: keyof Channels; label: string; help: string }[] = [
  { key: "popup", label: "Pop-up", help: "A note in the corner of the admin, with a link to it." },
  { key: "sound", label: "Sound", help: "Plays once, even if the admin is in a background tab." },
  { key: "desktop", label: "Desktop alert", help: "Your computer's own notification while the admin is in the background." },
];
const box = "size-4 accent-[var(--color-accent)]";

/** Admin → Notification settings: how live updates reach the signed-in person. Personal, not shop-wide. */
export default function NotificationSettings() {
  const { push } = useToast();
  const { mode, setPrefs: applyLive } = useLiveStatus();
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("default");

  useEffect(() => {
    apiFetch<Loaded>("/admin/live/preferences").then(
      (r) => {
        setLoaded(r);
        setPrefs(r.prefs);
      },
      (e) => setError(e.message),
    );
    setPermission(typeof Notification === "undefined" ? "unsupported" : Notification.permission);
  }, []);

  if (!prefs || !loaded) {
    return (
      <div>
        <PageHeader title="Notification settings" description="How new orders, messages and other updates reach you." />
        {error ? <Alert tone="danger">{error}</Alert> : <div className="skeleton h-64" />}
      </div>
    );
  }

  const cats = Object.keys(loaded.categories) as LiveCategory[];
  const setChannel = (cat: LiveCategory, ch: keyof Channels, on: boolean) =>
    setPrefs({ ...prefs, categories: { ...prefs.categories, [cat]: { ...prefs.categories[cat], [ch]: on } } });
  const setColumn = (ch: keyof Channels, on: boolean) =>
    setPrefs({ ...prefs, categories: Object.fromEntries(cats.map((c) => [c, { ...prefs.categories[c], [ch]: on }])) as NotificationPrefs["categories"] });
  const changed = JSON.stringify(prefs) !== JSON.stringify(loaded.prefs);
  const wantsDesktop = cats.some((c) => prefs.categories[c].desktop);

  async function save() {
    setBusy(true);
    try {
      const r = await apiFetch<Loaded>("/admin/live/preferences", { method: "PUT", body: JSON.stringify(prefs) });
      setLoaded(r);
      setPrefs(r.prefs);
      applyLive(r.prefs);
      push({ title: "Notification settings saved", description: "They apply to you only, in every browser you sign in to." });
    } catch (e) {
      push({ title: "Not saved", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  async function allowDesktop() {
    if (typeof Notification === "undefined") return;
    setPermission(await Notification.requestPermission());
  }

  return (
    <div>
      <PageHeader
        title="Notification settings"
        description="Choose how new orders, messages and other updates reach you while the admin is open. These are your own settings; other staff choose theirs."
        actions={
          <Button size="sm" disabled={busy || !changed} onClick={() => void save()}>
            {busy ? "Saving…" : "Save settings"}
          </Button>
        }
      />
      <p className="mb-4 text-sm text-muted" data-testid="live-mode">
        {mode === "stream" ? "Live updates are on: news arrives within a few seconds." : mode === "polling" ? "Live updates are checking every 10 seconds." : "Connecting to live updates…"}
      </p>

      <Panel>
        <PanelHeader title="What reaches you" description="The bell always counts everything. Tick how you want to hear about each kind of update." />
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[34rem] text-sm">
            <caption className="sr-only">Notification channels for each kind of update</caption>
            <thead>
              <tr className="border-b border-line text-left">
                <th scope="col" className="px-5 py-3 font-medium">
                  Update
                </th>
                {CHANNELS.map((c) => (
                  <th key={c.key} scope="col" className="w-32 px-3 py-3 text-center font-medium">
                    <span className="block">{c.label}</span>
                    <span className="mt-1 flex justify-center gap-2 text-xs font-normal">
                      <button type="button" className="text-accent underline-offset-4 hover:underline" onClick={() => setColumn(c.key, true)}>
                        All<span className="sr-only"> {c.label.toLowerCase()}</span>
                      </button>
                      <button type="button" className="text-accent underline-offset-4 hover:underline" onClick={() => setColumn(c.key, false)}>
                        None<span className="sr-only"> {c.label.toLowerCase()}</span>
                      </button>
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {cats.map((cat) => (
                <tr key={cat}>
                  <th scope="row" className="px-5 py-3 text-left font-normal">
                    {loaded.categories[cat]}
                  </th>
                  {CHANNELS.map((c) => (
                    <td key={c.key} className="px-3 py-3 text-center">
                      <input
                        type="checkbox"
                        className={box}
                        aria-label={`${c.label}: ${loaded.categories[cat]}`}
                        checked={prefs.categories[cat][c.key]}
                        onChange={(e) => setChannel(cat, c.key, e.target.checked)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <PanelBody className="border-t border-line text-xs text-muted">{CHANNELS.map((c) => `${c.label}: ${c.help}`).join(" ")}</PanelBody>
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Sound" description="Played for the updates ticked under Sound." />
          <PanelBody className="grid gap-4">
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Sound" className="w-40">
                {(p) => (
                  <Select {...p} value={prefs.sound} onChange={(e) => setPrefs({ ...prefs, sound: e.target.value as SoundName })}>
                    {(Object.keys(SOUND_LABELS) as SoundName[]).map((s) => (
                      <option key={s} value={s}>
                        {SOUND_LABELS[s]}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Button size="sm" variant="secondary" onClick={() => playSound(prefs.sound, Math.max(prefs.volume, 1))}>
                Play test sound
              </Button>
            </div>
            <p className="text-xs text-muted">Browsers only allow sound after you have clicked somewhere in the admin since opening it.</p>
            <Field label={`Volume (${prefs.volume}%)`} hint="0 turns sounds off.">
              {(p) => (
                <input
                  {...p}
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={prefs.volume}
                  onChange={(e) => setPrefs({ ...prefs, volume: Number(e.target.value) })}
                  className="w-full max-w-xs accent-[var(--color-accent)]"
                />
              )}
            </Field>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Desktop alerts and pages" />
          <PanelBody className="grid gap-4 text-sm">
            <div>
              <p className="font-medium">Desktop alerts in this browser</p>
              <p className="text-muted" data-testid="desktop-permission">
                {permission === "granted"
                  ? "Allowed. Alerts show while the admin is in a background tab."
                  : permission === "denied"
                    ? "Blocked in this browser. Allow notifications for this site in the browser's site settings."
                    : permission === "unsupported"
                      ? "This browser can't show desktop alerts."
                      : "Not allowed yet. Your browser will ask once."}
              </p>
              {permission === "default" && (
                <Button size="sm" variant="secondary" className="mt-2" onClick={() => void allowDesktop()}>
                  Allow desktop alerts
                </Button>
              )}
              {wantsDesktop && permission !== "granted" && permission !== "unsupported" && (
                <Alert tone="info" className="mt-2">
                  Some updates are ticked for desktop alerts, but this browser hasn&apos;t allowed them yet.
                </Alert>
              )}
            </div>
            <label className="flex items-start gap-3">
              <input type="checkbox" className={`${box} mt-0.5`} checked={prefs.refresh_bars} onChange={(e) => setPrefs({ ...prefs, refresh_bars: e.target.checked })} />
              <span>
                <span className="font-medium">&ldquo;Updates available&rdquo; on pages</span>
                <span className="block text-muted">A bar with Refresh above Orders, Messages and other lists, and &ldquo;changed since you opened it&rdquo; on an order or product.</span>
              </span>
            </label>
            <label className="flex items-start gap-3">
              <input type="checkbox" className={`${box} mt-0.5`} checked={prefs.new_version} onChange={(e) => setPrefs({ ...prefs, new_version: e.target.checked })} />
              <span>
                <span className="font-medium">Tell me when a new version of the admin is out</span>
                <span className="block text-muted">After a deploy, a bar at the top asks you to refresh.</span>
              </span>
            </label>
          </PanelBody>
        </Panel>
      </div>

      <div className="mt-6">
        <Button disabled={busy || !changed} onClick={() => void save()}>
          {busy ? "Saving…" : "Save settings"}
        </Button>
      </div>
    </div>
  );
}
