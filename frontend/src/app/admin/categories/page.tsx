"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { CategoryNode } from "@/lib/types";
import { useCategoryTree, type CategoryOption } from "@/components/admin/useCategoryOptions";
import { ConfirmDialog } from "@/components/admin/ui/Modal";
import { Icon } from "@/components/admin/ui/Icon";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

/**
 * Category tree editor. Reordering uses the same /categories/reorder endpoint a
 * drag-and-drop UI would call; here it's driven by "move up/down" buttons, which
 * are also keyboard-accessible.
 */
export default function CategoriesAdmin() {
  const { tree, options, reload } = useCategoryTree();
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<CategoryNode | null>(null);
  const [deleting, setDeleting] = useState<CategoryNode | null>(null);
  const { push } = useToast();

  async function run(fn: () => Promise<unknown>, done?: string) {
    setError("");
    try {
      await fn();
      reload();
      if (done) push({ title: done });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  }

  function move(siblings: CategoryNode[], index: number, delta: -1 | 1) {
    const target = index + delta;
    if (target < 0 || target >= siblings.length) return;
    const reordered = [...siblings];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    const items = reordered.map((c, i) => ({ id: c.id, parent_id: c.parent_id, sort_order: i }));
    return run(() => apiFetch("/categories/reorder", { method: "POST", body: JSON.stringify({ items }) }));
  }

  function renderLevel(nodes: CategoryNode[]): React.ReactNode {
    return (
      <ul className="space-y-1">
        {nodes.map((node, i) => (
          <li key={node.id}>
            <div className={`flex items-center gap-2 rounded-[var(--radius-control)] px-2 py-1.5 hover:bg-canvas ${editing?.id === node.id ? "bg-accent-soft/60" : ""}`}>
              <span className="min-w-0 flex-1 truncate text-sm">
                <span className="font-medium" data-testid="category-name">{node.name}</span> <span className="text-xs text-muted">/{node.slug}</span>
              </span>
              {!node.is_active && <Pill tone="neutral">Hidden</Pill>}
              <Button size="sm" variant="ghost" className="size-8 px-0" disabled={i === 0} onClick={() => move(nodes, i, -1)}>
                <Icon name="arrowUp" className="size-4" />
                <span className="sr-only">Move {node.name} up</span>
              </Button>
              <Button size="sm" variant="ghost" className="size-8 px-0" disabled={i === nodes.length - 1} onClick={() => move(nodes, i, 1)}>
                <Icon name="arrowDown" className="size-4" />
                <span className="sr-only">Move {node.name} down</span>
              </Button>
              <Button size="sm" variant="secondary" className="h-8" onClick={() => setEditing(node)}>
                Edit<span className="sr-only"> {node.name}</span>
              </Button>
            </div>
            {node.children.length > 0 && <div className="ml-4 border-l border-line pl-3">{renderLevel(node.children)}</div>}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div>
      <PageHeader
        title="Categories"
        description="The shop menu is built from this tree. Use the arrows to reorder. Hidden categories do not appear in the shop."
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <Panel aria-label="Category tree">
          <PanelHeader title="Category tree" description={`${options.length} categories`} />
          <div className="p-3">{tree.length ? renderLevel(tree) : <p className="p-2 text-sm text-muted">No categories yet. Add the first one.</p>}</div>
        </Panel>

        {editing ? (
          <CategoryForm
            key={editing.id}
            title={`Edit “${editing.name}”`}
            initial={editing}
            options={options.filter((o) => o.id !== editing.id)}
            onCancel={() => setEditing(null)}
            onSave={(body) =>
              run(async () => {
                await apiFetch(`/categories/${editing.id}`, { method: "PATCH", body: JSON.stringify(body) });
                setEditing(null);
              }, "Saved")
            }
            onDelete={() => setDeleting(editing)}
          />
        ) : (
          <CategoryForm
            title="Add a category"
            options={options}
            onSave={(body) => run(() => apiFetch("/categories", { method: "POST", body: JSON.stringify(body) }), "Category added")}
          />
        )}
      </div>

      <ConfirmDialog
        open={!!deleting}
        title={`Delete “${deleting?.name ?? ""}”?`}
        message="A category can only be deleted once it has no products and no sub-categories. This can't be undone."
        confirmLabel="Delete category"
        onCancel={() => setDeleting(null)}
        onConfirm={() => {
          const target = deleting;
          setDeleting(null);
          if (!target) return;
          void run(async () => {
            await apiFetch(`/categories/${target.id}`, { method: "DELETE" });
            setEditing(null);
          }, "Category deleted");
        }}
      />
    </div>
  );
}

function CategoryForm({
  title,
  initial,
  options,
  onSave,
  onCancel,
  onDelete,
}: {
  title: string;
  initial?: CategoryNode;
  options: CategoryOption[];
  onSave: (body: Record<string, unknown>) => void;
  onCancel?: () => void;
  onDelete?: () => void;
}) {
  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const parent = String(fd.get("parent_id") || "");
    const body: Record<string, unknown> = {
      name: String(fd.get("name")).trim(),
      description: String(fd.get("description") || "").trim() || null,
      parent_id: parent ? Number(parent) : null,
      is_active: fd.get("is_active") === "on",
    };
    const slug = String(fd.get("slug") || "").trim();
    if (slug) body.slug = slug;
    onSave(body);
    if (!initial) e.currentTarget.reset();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4 rounded-[var(--radius-card)] border border-line bg-surface p-5 lg:sticky lg:top-20">
      <h2 className="text-base">{title}</h2>
      <div className="grid gap-4">
        <Field label="Name">{(p) => <Input {...p} name="name" required defaultValue={initial?.name} />}</Field>
        <Field label="Slug" hint="Optional; generated from the name.">
          {(p) => <Input {...p} name="slug" defaultValue={initial?.slug} pattern="[a-z0-9]+(-[a-z0-9]+)*" />}
        </Field>
        <Field label="Parent">
          {(p) => (
            <Select {...p} name="parent_id" defaultValue={initial?.parent_id ?? ""}>
              <option value="">— Top level —</option>
              {options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Description">{(p) => <Input {...p} name="description" defaultValue={initial?.description ?? ""} />}</Field>
      </div>
      <label className="flex items-center gap-2.5 text-sm">
        <input type="checkbox" name="is_active" defaultChecked={initial?.is_active ?? true} className="size-4 accent-[var(--color-accent)]" />
        Visible in the shop
      </label>
      <div className="flex gap-2">
        <Button type="submit" size="sm" className="h-9">
          {initial ? "Save changes" : "Add category"}
        </Button>
        {onCancel && (
          <Button variant="ghost" size="sm" className="h-9" onClick={onCancel}>
            Cancel
          </Button>
        )}
        {onDelete && (
          <Button variant="ghost" size="sm" onClick={onDelete} className="ml-auto h-9 text-danger hover:bg-danger/10">
            Delete
          </Button>
        )}
      </div>
    </form>
  );
}
