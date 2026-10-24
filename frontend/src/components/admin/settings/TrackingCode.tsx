"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { IconButton, RowActions } from "@/components/admin/ui/IconButton";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Icon } from "@/components/admin/ui/Icon";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

export interface Snippet {
  id: string;
  name: string;
  placement: "head" | "body";
  code: string;
  enabled: boolean;
  require_consent: boolean;
}

type Mode = "view" | "edit" | "add";
const SECTIONS = [
  { placement: "head" as const, title: "Header snippets", about: "Added to the top (the <head>) of every shop page. Most analytics and pixel snippets go here.", empty: "No header snippets yet." },
  { placement: "body" as const, title: "Footer snippets", about: "Added at the end of every shop page. Chat boxes and other “before </body>” snippets go here.", empty: "No footer snippets yet." },
];

function newId(): string {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return "s" + Array.from(bytes, (b) => b.toString(36).padStart(2, "0")).join("");
}

/** Named snippets (Google Analytics, a pixel, a chat box) in two tables: header and footer. */
export function TrackingCode({ initial, onSaved }: { initial: Snippet[]; onSaved: (snippets: Snippet[]) => void }) {
  const { push } = useToast();
  const [items, setItems] = useState<Snippet[]>(initial);
  const [dialog, setDialog] = useState<{ mode: Mode; draft: Snippet } | null>(null);
  const [deleting, setDeleting] = useState<Snippet | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  async function persist(next: Snippet[], done: string, detail: string): Promise<boolean> {
    setBusy(true);
    setProblem("");
    try {
      const res = await apiFetch<{ settings: { scripts: { snippets: Snippet[] } } }>("/admin/settings/scripts", {
        method: "PUT",
        body: JSON.stringify({ snippets: next }),
      });
      const saved = res.settings.scripts.snippets;
      setItems(saved);
      onSaved(saved);
      push({ title: done, description: detail });
      return true;
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Couldn't save");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function open(mode: Mode, draft: Snippet) {
    setProblem("");
    setDialog({ mode, draft });
  }
  const blank = (placement: "head" | "body"): Snippet => ({ id: newId(), name: "", placement, code: "", enabled: true, require_consent: true });

  async function save() {
    if (!dialog) return;
    const d = { ...dialog.draft, name: dialog.draft.name.trim(), code: dialog.draft.code.trim() };
    if (!d.name) return setProblem("Give the snippet a name.");
    if (!d.code) return setProblem("Paste the snippet code.");
    const exists = items.some((x) => x.id === d.id);
    const next = exists ? items.map((x) => (x.id === d.id ? d : x)) : [...items, d];
    if (await persist(next, exists ? "Snippet saved" : "Snippet added", d.name)) setDialog(null);
  }

  const columns = (placement: "head" | "body"): Column<Snippet>[] => [
    {
      key: "name",
      header: "Name",
      cell: (r) => (
        <button type="button" onClick={() => open("view", r)} className="font-medium text-ink underline-offset-4 hover:underline focus-visible:outline-2">
          {r.name}
        </button>
      ),
    },
    { key: "status", header: "Status", cell: (r) => (r.enabled ? <Pill tone="success">On</Pill> : <Pill tone="neutral">Off</Pill>) },
    {
      key: "consent",
      header: "Runs",
      hide: "sm",
      cell: (r) => <span className="text-muted">{r.require_consent ? "After cookie consent" : "For every visitor"}</span>,
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (r) => (
        <RowActions>
          <IconButton
            icon={r.enabled ? "pause" : "play"}
            label={r.enabled ? `Turn off ${r.name}` : `Turn on ${r.name}`}
            disabled={busy}
            onClick={() => persist(items.map((x) => (x.id === r.id ? { ...x, enabled: !x.enabled } : x)), r.enabled ? "Snippet turned off" : "Snippet turned on", r.name)}
          />
          <IconButton icon="eye" label={`View ${r.name}`} onClick={() => open("view", r)} />
          <IconButton icon="edit" label={`Edit ${r.name}`} onClick={() => open("edit", r)} />
          <IconButton icon="trash" tone="danger" label={`Delete ${r.name}`} onClick={() => setDeleting(r)} />
        </RowActions>
      ),
    },
  ];

  const d = dialog?.draft;
  const readOnly = dialog?.mode === "view";
  const set = (patch: Partial<Snippet>) => setDialog((cur) => (cur ? { ...cur, draft: { ...cur.draft, ...patch } } : cur));

  return (
    <div className="space-y-6">
      {SECTIONS.map((sec) => {
        const rows = items.filter((x) => x.placement === sec.placement);
        return (
          <Panel key={sec.placement}>
            <PanelHeader
              title={sec.title}
              description={sec.about}
              actions={
                <Button size="sm" onClick={() => open("add", blank(sec.placement))}>
                  <Icon name="plus" className="size-4" />
                  Add {sec.placement === "head" ? "header" : "footer"} snippet
                </Button>
              }
            />
            {rows.length === 0 ? (
              <PanelBody>
                <p className="text-sm text-muted">{sec.empty}</p>
              </PanelBody>
            ) : (
              <DataTable columns={columns(sec.placement)} rows={rows} rowKey={(r) => r.id} caption={sec.title} />
            )}
          </Panel>
        );
      })}
      <p className="text-sm text-muted">Snippets are added to the shop only, never to this admin. Only paste code from services you trust: it runs on every page.</p>

      <Modal
        open={!!dialog}
        onClose={() => setDialog(null)}
        size="lg"
        title={dialog?.mode === "add" ? "Add snippet" : dialog?.mode === "edit" ? "Edit snippet" : (d?.name ?? "Snippet")}
        description={readOnly ? "Read only. Choose Edit to change it." : "Paste the code exactly as the service gives it."}
        footer={
          readOnly ? (
            <>
              <Button variant="secondary" onClick={() => setDialog(null)}>
                Close
              </Button>
              <Button onClick={() => d && open("edit", d)}>Edit snippet</Button>
            </>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setDialog(null)} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={save} disabled={busy}>
                {dialog?.mode === "add" ? "Add snippet" : "Save snippet"}
              </Button>
            </>
          )
        }
      >
        {d && (
          <div className="space-y-4">
            {problem && <Alert tone="danger">{problem}</Alert>}
            <Field label="Name" hint="A label for you, such as Google Analytics.">
              {(p) => <Input {...p} value={d.name} onChange={(e) => set({ name: e.target.value })} maxLength={80} readOnly={readOnly} />}
            </Field>
            <Field label="Where it goes">
              {(p) => (
                <Select {...p} value={d.placement} onChange={(e) => set({ placement: e.target.value as "head" | "body" })} disabled={readOnly}>
                  <option value="head">Header (top of every page)</option>
                  <option value="body">Footer (end of every page)</option>
                </Select>
              )}
            </Field>
            <Field label="Code">
              {(p) => (
                <Textarea
                  {...p}
                  value={d.code}
                  onChange={(e) => set({ code: e.target.value })}
                  maxLength={20000}
                  spellCheck={false}
                  readOnly={readOnly}
                  placeholder="<script>…</script>"
                  className="min-h-48 font-mono text-xs"
                />
              )}
            </Field>
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={d.enabled} disabled={readOnly} onChange={(e) => set({ enabled: e.target.checked })} />
              <span>Turned on</span>
            </label>
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={d.require_consent} disabled={readOnly} onChange={(e) => set({ require_consent: e.target.checked })} />
              <span>Wait for the visitor to accept the cookie banner</span>
            </label>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title={`Delete ${deleting?.name ?? "snippet"}?`}
        message="The code stops being added to the shop straight away."
        confirmLabel="Delete snippet"
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (!deleting) return;
          if (await persist(items.filter((x) => x.id !== deleting.id), "Snippet deleted", deleting.name)) setDeleting(null);
          else setDeleting(null);
        }}
      />
      {problem && !dialog && (
        <Alert tone="danger" className="mt-2">
          {problem}
        </Alert>
      )}
    </div>
  );
}
