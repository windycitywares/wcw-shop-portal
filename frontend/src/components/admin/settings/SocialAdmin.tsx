"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { SOCIAL_PLATFORMS, socialOf } from "@/lib/socialPlatforms";
import { SocialGlyph } from "@/components/ui/SocialLinks";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { IconButton, RowActions } from "@/components/admin/ui/IconButton";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

export interface SocialRow {
  id: string;
  platform: string;
  handle: string;
  url: string;
  enabled: boolean;
}

type Mode = "view" | "edit" | "add";

function newId(): string {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return "s" + Array.from(bytes, (b) => b.toString(36).padStart(2, "0")).join("");
}

/** The owner's social media accounts: one table, with view, edit, on/off, reorder and delete on each row. */
export function SocialAdmin({ initial, onSaved }: { initial: SocialRow[]; onSaved: (rows: SocialRow[]) => void }) {
  const { push } = useToast();
  const [items, setItems] = useState<SocialRow[]>(initial);
  const [dialog, setDialog] = useState<{ mode: Mode; draft: SocialRow } | null>(null);
  const [deleting, setDeleting] = useState<SocialRow | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  async function persist(next: SocialRow[], done: string, detail: string): Promise<boolean> {
    setBusy(true);
    setProblem("");
    try {
      const res = await apiFetch<{ settings: { social: { accounts: SocialRow[] } } }>("/admin/settings/social", {
        method: "PUT",
        body: JSON.stringify({ accounts: next }),
      });
      const saved = res.settings.social.accounts;
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

  const blank = (): SocialRow => ({ id: newId(), platform: "instagram", handle: "", url: "", enabled: true });
  const open = (mode: Mode, draft: SocialRow) => {
    setProblem("");
    setDialog({ mode, draft });
  };
  const set = (patch: Partial<SocialRow>) => setDialog((cur) => (cur ? { ...cur, draft: { ...cur.draft, ...patch } } : cur));
  const label = (r: SocialRow) => r.handle || socialOf(r.platform).label;

  async function save() {
    if (!dialog) return;
    const d = { ...dialog.draft, handle: dialog.draft.handle.trim(), url: dialog.draft.url.trim() };
    if (!d.url) return setProblem("Paste the address of your profile.");
    const exists = items.some((x) => x.id === d.id);
    const next = exists ? items.map((x) => (x.id === d.id ? d : x)) : [...items, d];
    if (await persist(next, exists ? "Account saved" : "Account added", label(d))) setDialog(null);
  }

  function move(index: number, by: -1 | 1) {
    const next = [...items];
    const [row] = next.splice(index, 1);
    next.splice(index + by, 0, row);
    void persist(next, "Account moved", label(row));
  }

  const columns: Column<SocialRow>[] = [
    {
      key: "name",
      header: "Account",
      cell: (r) => (
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full bg-canvas text-ink">
            <SocialGlyph platform={r.platform} className="size-4" />
          </span>
          <button type="button" onClick={() => open("view", r)} className="font-medium text-ink underline-offset-4 hover:underline focus-visible:outline-2">
            {label(r)}
          </button>
        </div>
      ),
    },
    { key: "platform", header: "Network", hide: "sm", cell: (r) => <span className="text-muted">{socialOf(r.platform).label}</span> },
    { key: "status", header: "Status", cell: (r) => (r.enabled ? <Pill tone="success">Shown</Pill> : <Pill tone="neutral">Hidden</Pill>) },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (r) => {
        const i = items.findIndex((x) => x.id === r.id);
        return (
          <RowActions>
            <IconButton icon="arrowUp" label={`Move ${label(r)} up`} disabled={busy || i === 0} onClick={() => move(i, -1)} />
            <IconButton icon="arrowDown" label={`Move ${label(r)} down`} disabled={busy || i === items.length - 1} onClick={() => move(i, 1)} />
            <IconButton
              icon={r.enabled ? "pause" : "play"}
              label={r.enabled ? `Hide ${label(r)}` : `Show ${label(r)}`}
              disabled={busy}
              onClick={() => persist(items.map((x) => (x.id === r.id ? { ...x, enabled: !x.enabled } : x)), r.enabled ? "Account hidden" : "Account shown", label(r))}
            />
            <IconButton icon="eye" label={`View ${label(r)}`} onClick={() => open("view", r)} />
            <IconButton icon="edit" label={`Edit ${label(r)}`} onClick={() => open("edit", r)} />
            <IconButton icon="trash" tone="danger" label={`Delete ${label(r)}`} onClick={() => setDeleting(r)} />
          </RowActions>
        );
      },
    },
  ];

  const d = dialog?.draft;
  const readOnly = dialog?.mode === "view";

  return (
    <div className="space-y-6">
      <Panel>
        <PanelHeader
          title="Your social media accounts"
          description="Shown in this order as icons in the bar above the header, and as Follow us buttons with your handle in the footer and on the home page. The same list appears on windycitywares.com."
          actions={
            <Button size="sm" onClick={() => open("add", blank())}>
              <Icon name="plus" className="size-4" />
              Add account
            </Button>
          }
        />
        {items.length === 0 ? (
          <PanelBody>
            <p className="text-sm text-muted">No accounts yet. Add one and it appears on both sites within a few minutes.</p>
          </PanelBody>
        ) : (
          <DataTable columns={columns} rows={items} rowKey={(r) => r.id} caption="Your social media accounts" />
        )}
      </Panel>
      {problem && !dialog && <Alert tone="danger">{problem}</Alert>}

      <Modal
        open={!!dialog}
        onClose={() => setDialog(null)}
        size="md"
        title={dialog?.mode === "add" ? "Add account" : dialog?.mode === "edit" ? "Edit account" : (d ? label(d) : "Account")}
        description={readOnly ? "Read only. Choose Edit to change it." : "Pick the network, then paste the address of your profile or page."}
        footer={
          readOnly ? (
            <>
              <Button variant="secondary" onClick={() => setDialog(null)}>
                Close
              </Button>
              <Button onClick={() => d && open("edit", d)}>Edit account</Button>
            </>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setDialog(null)} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={save} disabled={busy}>
                {dialog?.mode === "add" ? "Add account" : "Save account"}
              </Button>
            </>
          )
        }
      >
        {d && (
          <div className="space-y-4">
            {problem && <Alert tone="danger">{problem}</Alert>}
            <div className="flex items-center gap-3 rounded-[var(--radius-card)] bg-canvas p-3" aria-label="How the button will look">
              <span className="inline-flex min-h-11 items-center gap-2 rounded-full border border-line bg-surface px-4 text-sm font-medium text-ink">
                <SocialGlyph platform={d.platform} className="size-[1.125rem]" />
                {d.handle || socialOf(d.platform).label}
              </span>
            </div>
            <Field label="Network">
              {(p) => (
                <Select {...p} value={d.platform} onChange={(e) => set({ platform: e.target.value })} disabled={readOnly}>
                  {SOCIAL_PLATFORMS.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Handle" hint="What visitors see on the button, such as @windycityware. Leave empty to show the network's name.">
              {(p) => <Input {...p} value={d.handle} onChange={(e) => set({ handle: e.target.value })} maxLength={60} readOnly={readOnly} placeholder="@windycityware" />}
            </Field>
            <Field label="Web address" hint="The full https:// address of your profile (parts with ? or # are fine). It must belong to the network you picked. Type just # if the account is not open yet: visitors then see it greyed out as “Coming soon”.">
              {(p) => <Input {...p} inputMode="url" value={d.url} onChange={(e) => set({ url: e.target.value })} maxLength={500} readOnly={readOnly} placeholder="https://www.instagram.com/windycityware/" />}
            </Field>
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={d.enabled} disabled={readOnly} onChange={(e) => set({ enabled: e.target.checked })} />
              <span>Show this account on the site</span>
            </label>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title={`Delete ${deleting ? label(deleting) : "account"}?`}
        message="It disappears from both sites within a few minutes."
        confirmLabel="Delete account"
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (!deleting) return;
          await persist(items.filter((x) => x.id !== deleting.id), "Account deleted", label(deleting));
          setDeleting(null);
        }}
      />
    </div>
  );
}
