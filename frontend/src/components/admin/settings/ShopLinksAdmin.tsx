"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { SHOP_PLATFORMS, platformOf } from "@/lib/shopPlatforms";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { IconButton, RowActions } from "@/components/admin/ui/IconButton";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

export interface ShopLinkRow {
  id: string;
  platform: string;
  name: string;
  url: string;
  blurb: string | null;
  image_url: string | null;
  enabled: boolean;
}

type Mode = "view" | "edit" | "add";

function newId(): string {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return "l" + Array.from(bytes, (b) => b.toString(36).padStart(2, "0")).join("");
}

/** The colour badge visitors will see for this platform. */
function Badge({ platform, name }: { platform: string; name: string }) {
  const p = platformOf(platform);
  return (
    <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full text-sm font-bold" style={{ background: p.bg, color: p.fg }}>
      {(p.id === "other" ? name || "?" : p.label).charAt(0).toUpperCase()}
    </span>
  );
}

/** The owner's shops on other marketplaces: one table, with view, edit, on/off, reorder and delete on each row. */
export function ShopLinksAdmin({ initial, onSaved }: { initial: ShopLinkRow[]; onSaved: (links: ShopLinkRow[]) => void }) {
  const { push } = useToast();
  const [items, setItems] = useState<ShopLinkRow[]>(initial);
  const [dialog, setDialog] = useState<{ mode: Mode; draft: ShopLinkRow } | null>(null);
  const [deleting, setDeleting] = useState<ShopLinkRow | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  async function persist(next: ShopLinkRow[], done: string, detail: string): Promise<boolean> {
    setBusy(true);
    setProblem("");
    try {
      const res = await apiFetch<{ settings: { shop_links: { links: ShopLinkRow[] } } }>("/admin/settings/shop_links", {
        method: "PUT",
        body: JSON.stringify({ links: next }),
      });
      const saved = res.settings.shop_links.links;
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

  const blank = (): ShopLinkRow => ({ id: newId(), platform: "etsy", name: "", url: "", blurb: null, image_url: null, enabled: true });
  const open = (mode: Mode, draft: ShopLinkRow) => {
    setProblem("");
    setDialog({ mode, draft });
  };
  const set = (patch: Partial<ShopLinkRow>) => setDialog((cur) => (cur ? { ...cur, draft: { ...cur.draft, ...patch } } : cur));

  async function save() {
    if (!dialog) return;
    const d = { ...dialog.draft, name: dialog.draft.name.trim(), url: dialog.draft.url.trim(), blurb: dialog.draft.blurb?.trim() || null, image_url: dialog.draft.image_url?.trim() || null };
    if (!d.name) return setProblem("Give the shop a name.");
    if (!d.url) return setProblem("Paste the shop's web address.");
    const exists = items.some((x) => x.id === d.id);
    const next = exists ? items.map((x) => (x.id === d.id ? d : x)) : [...items, d];
    if (await persist(next, exists ? "Shop saved" : "Shop added", d.name)) setDialog(null);
  }

  function move(index: number, by: -1 | 1) {
    const next = [...items];
    const [row] = next.splice(index, 1);
    next.splice(index + by, 0, row);
    void persist(next, "Shop moved", row.name);
  }

  const columns: Column<ShopLinkRow>[] = [
    {
      key: "name",
      header: "Shop",
      cell: (r) => (
        <div className="flex items-center gap-3">
          <Badge platform={r.platform} name={r.name} />
          <button type="button" onClick={() => open("view", r)} className="font-medium text-ink underline-offset-4 hover:underline focus-visible:outline-2">
            {r.name}
          </button>
        </div>
      ),
    },
    { key: "platform", header: "Marketplace", hide: "sm", cell: (r) => <span className="text-muted">{platformOf(r.platform).label}</span> },
    { key: "status", header: "Status", cell: (r) => (r.enabled ? <Pill tone="success">Shown</Pill> : <Pill tone="neutral">Hidden</Pill>) },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (r) => {
        const i = items.findIndex((x) => x.id === r.id);
        return (
          <RowActions>
            <IconButton icon="arrowUp" label={`Move ${r.name} up`} disabled={busy || i === 0} onClick={() => move(i, -1)} />
            <IconButton icon="arrowDown" label={`Move ${r.name} down`} disabled={busy || i === items.length - 1} onClick={() => move(i, 1)} />
            <IconButton
              icon={r.enabled ? "pause" : "play"}
              label={r.enabled ? `Hide ${r.name}` : `Show ${r.name}`}
              disabled={busy}
              onClick={() => persist(items.map((x) => (x.id === r.id ? { ...x, enabled: !x.enabled } : x)), r.enabled ? "Shop hidden" : "Shop shown", r.name)}
            />
            <IconButton icon="eye" label={`View ${r.name}`} onClick={() => open("view", r)} />
            <IconButton icon="edit" label={`Edit ${r.name}`} onClick={() => open("edit", r)} />
            <IconButton icon="trash" tone="danger" label={`Delete ${r.name}`} onClick={() => setDeleting(r)} />
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
          title="Your shops"
          description="Shown in this order as tiles on the home page, and as links in the footer. Hover a tile to see its short description."
          actions={
            <Button size="sm" onClick={() => open("add", blank())}>
              <Icon name="plus" className="size-4" />
              Add shop
            </Button>
          }
        />
        {items.length === 0 ? (
          <PanelBody>
            <p className="text-sm text-muted">No shops yet. Until you add one, the home page shows the Etsy shop link from the site settings.</p>
          </PanelBody>
        ) : (
          <DataTable columns={columns} rows={items} rowKey={(r) => r.id} caption="Your shops on other marketplaces" />
        )}
      </Panel>
      {problem && !dialog && <Alert tone="danger">{problem}</Alert>}

      <Modal
        open={!!dialog}
        onClose={() => setDialog(null)}
        size="md"
        title={dialog?.mode === "add" ? "Add shop" : dialog?.mode === "edit" ? "Edit shop" : (d?.name ?? "Shop")}
        description={readOnly ? "Read only. Choose Edit to change it." : "Pick the marketplace, then paste the address of your shop page."}
        footer={
          readOnly ? (
            <>
              <Button variant="secondary" onClick={() => setDialog(null)}>
                Close
              </Button>
              <Button onClick={() => d && open("edit", d)}>Edit shop</Button>
            </>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setDialog(null)} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={save} disabled={busy}>
                {dialog?.mode === "add" ? "Add shop" : "Save shop"}
              </Button>
            </>
          )
        }
      >
        {d && (
          <div className="space-y-4">
            {problem && <Alert tone="danger">{problem}</Alert>}
            <div className="flex items-center gap-3 rounded-[var(--radius-card)] bg-canvas p-3" aria-label="How the tile will look">
              <Badge platform={d.platform} name={d.name} />
              <div className="min-w-0 text-sm">
                <p className="truncate font-semibold text-ink">{d.name || "Shop name"}</p>
                <p className="text-muted">{d.platform === "other" ? "Opens in a new tab" : `on ${platformOf(d.platform).label}`}</p>
              </div>
            </div>
            <Field label="Marketplace">
              {(p) => (
                <Select {...p} value={d.platform} onChange={(e) => set({ platform: e.target.value })} disabled={readOnly}>
                  {SHOP_PLATFORMS.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Name" hint="What visitors see, such as Windy City Wares on Etsy.">
              {(p) => <Input {...p} value={d.name} onChange={(e) => set({ name: e.target.value })} maxLength={60} readOnly={readOnly} />}
            </Field>
            <Field label="Web address" hint="The full https:// address of your shop page. It must belong to the marketplace you picked.">
              {(p) => <Input {...p} type="url" inputMode="url" value={d.url} onChange={(e) => set({ url: e.target.value })} maxLength={500} readOnly={readOnly} placeholder="https://www.etsy.com/shop/YourShop" />}
            </Field>
            <Field label="Short description" hint={`Shown when a visitor hovers the tile. ${(d.blurb ?? "").length}/160`}>
              {(p) => <Textarea {...p} value={d.blurb ?? ""} onChange={(e) => set({ blurb: e.target.value || null })} maxLength={160} readOnly={readOnly} className="min-h-20" />}
            </Field>
            <Field label="Logo or picture address (optional)" hint="An https:// image address. Leave empty to use the coloured badge.">
              {(p) => <Input {...p} type="url" inputMode="url" value={d.image_url ?? ""} onChange={(e) => set({ image_url: e.target.value || null })} maxLength={500} readOnly={readOnly} />}
            </Field>
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={d.enabled} disabled={readOnly} onChange={(e) => set({ enabled: e.target.checked })} />
              <span>Show this shop on the site</span>
            </label>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title={`Delete ${deleting?.name ?? "shop"}?`}
        message="It disappears from the home page and footer straight away."
        confirmLabel="Delete shop"
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (!deleting) return;
          await persist(items.filter((x) => x.id !== deleting.id), "Shop deleted", deleting.name);
          setDeleting(null);
        }}
      />
    </div>
  );
}
