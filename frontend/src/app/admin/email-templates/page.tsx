"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/client-api";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Tabs } from "@/components/admin/ui/Tabs";
import { ConfirmDialog } from "@/components/admin/ui/Modal";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

type Parts = Partial<Record<"subject" | "intro" | "button" | "signoff", string>>;
interface Template {
  kind: string;
  label: string;
  description: string;
  placeholders: { name: string; help: string }[];
  languages: Record<string, { defaults: Parts; saved: Parts }>;
}
interface Catalog {
  parts: { key: keyof Parts; label: string }[];
  emails: Template[];
}

const LANGS = [
  { id: "en", label: "English" },
  { id: "es", label: "Spanish" },
  { id: "nl", label: "Dutch" },
];

export default function AdminEmailTemplates() {
  const { push } = useToast();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState("");
  const [kind, setKind] = useState("");
  const [lang, setLang] = useState("en");
  const [draft, setDraft] = useState<Parts>({});
  const [preview, setPreview] = useState<{ subject: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    apiFetch<Catalog>("/admin/email-templates").then(
      (c) => {
        setCatalog(c);
        setKind(c.emails[0]?.kind ?? "");
      },
      (e) => setError(e.message),
    );
  }, []);

  const current = catalog?.emails.find((e) => e.kind === kind);
  const saved = current?.languages[lang]?.saved;
  const defaults = current?.languages[lang]?.defaults ?? {};

  // Switching email or language starts from what is saved.
  useEffect(() => setDraft({ ...(saved ?? {}) }), [kind, lang, saved]);

  const refreshPreview = useCallback(
    (parts: Parts) => {
      if (!kind) return;
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        apiFetch<{ subject: string; text: string }>(`/admin/email-templates/${kind}/${lang}/preview`, { method: "POST", body: JSON.stringify(parts) }).then(setPreview, () => setPreview(null));
      }, 350);
    },
    [kind, lang],
  );
  useEffect(() => {
    refreshPreview(draft);
    return () => window.clearTimeout(timer.current);
  }, [draft, refreshPreview]);

  const changed = JSON.stringify(clean(draft)) !== JSON.stringify(clean(saved ?? {}));

  async function save(parts: Parts, verb: string) {
    setBusy(true);
    try {
      const res = await apiFetch<{ emails: Template[] }>(`/admin/email-templates/${kind}/${lang}`, { method: "PUT", body: JSON.stringify(parts) });
      setCatalog((c) => (c ? { ...c, emails: res.emails } : c));
      push({ title: `${verb} email wording`, description: `${current?.label} (${LANGS.find((l) => l.id === lang)?.label})` });
    } catch (e) {
      push({ title: "Couldn't save", description: e instanceof Error ? e.message : "", tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  async function sendTest() {
    try {
      const r = await apiFetch<{ detail: string }>(`/admin/email-templates/${kind}/${lang}/test`, { method: "POST", body: JSON.stringify(draft) });
      push({ title: "Test email sent", description: r.detail });
    } catch (e) {
      push({ title: "Test email not sent", description: e instanceof Error ? e.message : "", tone: "danger" });
    }
  }

  return (
    <div>
      <PageHeader
        title="Email templates"
        description="Change the wording of the emails customers receive. Links, codes, order lines and totals are added by the shop. Leave a box empty to keep the built-in wording."
        actions={
          <Link href="/admin/settings?tab=email" className="text-sm font-medium text-accent underline">
            Email sending settings
          </Link>
        }
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      {!catalog ? (
        <div className="skeleton h-64" />
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <nav aria-label="Emails" className="space-y-1">
            {catalog.emails.map((e) => (
              <button
                key={e.kind}
                type="button"
                onClick={() => setKind(e.kind)}
                aria-current={kind === e.kind ? "true" : undefined}
                className={`block w-full rounded-[var(--radius-control)] px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${kind === e.kind ? "bg-sand font-medium text-ink" : "text-muted hover:bg-sand/60 hover:text-ink"}`}
              >
                {e.label}
                {Object.values(e.languages).some((l) => Object.keys(l.saved).length > 0) && <span className="ml-2 text-xs text-accent">edited</span>}
              </button>
            ))}
          </nav>
          {current && (
            <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
              <Panel>
                <PanelHeader title={current.label} description={current.description} />
                <PanelBody className="space-y-4">
                  <Tabs tabs={LANGS} value={lang} onChange={setLang} label="Language" />
                  {catalog.parts.map((p) => (
                    <Field key={p.key} label={p.label}>
                      {(f) =>
                        p.key === "intro" || p.key === "signoff" ? (
                          <Textarea {...f} value={draft[p.key] ?? ""} placeholder={defaults[p.key] ?? ""} onChange={(e) => setDraft({ ...draft, [p.key]: e.target.value })} className="min-h-24" />
                        ) : (
                          <Input {...f} value={draft[p.key] ?? ""} placeholder={defaults[p.key] ?? ""} onChange={(e) => setDraft({ ...draft, [p.key]: e.target.value })} />
                        )
                      }
                    </Field>
                  ))}
                  {current.placeholders.length > 0 && (
                    <p className="text-xs text-muted">
                      You can use {current.placeholders.map((p, i) => (
                        <span key={p.name}>
                          {i > 0 && ", "}
                          <code>{`{${p.name}}`}</code> ({p.help})
                        </span>
                      ))}{" "}
                      in the subject and opening message.
                    </p>
                  )}
                  <div className="flex flex-wrap items-center gap-3 pt-2">
                    <Button disabled={busy || !changed} onClick={() => save(draft, "Saved")}>
                      Save changes
                    </Button>
                    <Button variant="secondary" onClick={sendTest}>
                      Send a test to me
                    </Button>
                    <Button variant="ghost" disabled={busy || Object.keys(clean(saved ?? {})).length === 0} onClick={() => setConfirmReset(true)}>
                      Reset to built-in wording
                    </Button>
                  </div>
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Preview" description={preview ? `Subject: ${preview.subject}` : "Shown with sample details (the plain-text version; the HTML email has the same words)."} />
                <PanelBody>
                  <div
                    role="region"
                    aria-label="Email preview"
                    tabIndex={0}
                    className="max-h-[34rem] overflow-auto whitespace-pre-wrap rounded-[var(--radius-control)] border border-line bg-white p-4 text-sm leading-relaxed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  >
                    {preview?.text ?? ""}
                  </div>
                </PanelBody>
              </Panel>
            </div>
          )}
        </div>
      )}
      <ConfirmDialog
        open={confirmReset}
        title="Reset to built-in wording?"
        message="Your changes to this email in this language will be removed."
        confirmLabel="Reset wording"
        busy={busy}
        onCancel={() => setConfirmReset(false)}
        onConfirm={async () => {
          await save({}, "Reset");
          setConfirmReset(false);
        }}
      />
    </div>
  );
}

function clean(p: Parts): Parts {
  return Object.fromEntries(Object.entries(p).filter(([, v]) => typeof v === "string" && v.trim() !== "").map(([k, v]) => [k, (v as string).trim()]));
}
