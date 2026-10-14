"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch, downloadFile } from "@/lib/client-api";
import type { ImporterInfo, ImportPreview, ImportSummary } from "@/lib/types";
import { formatAttribute, formatPrice } from "@/lib/utils";
import { useCategoryTree } from "@/components/admin/useCategoryOptions";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

const HOW_TO: Record<string, string> = {
  etsy: "Etsy → Shop Manager → Settings → Options → Download Data → “Download CSV” under Currently for Sale Listings.",
  amazon:
    "Seller Central → Inventory → Inventory Reports → “All Listings Report”, or Catalog → Add Products via Upload → download your inventory file.",
  spreadsheet: "Use the template below, or export the current catalog, edit it in Excel and import it back.",
};

export default function ImportPage() {
  const { can } = useAuth();
  const { options } = useCategoryTree();
  const [sources, setSources] = useState<ImporterInfo[]>([]);
  const [source, setSource] = useState("etsy");
  const [file, setFile] = useState<File | null>(null);
  const [categoryId, setCategoryId] = useState("");
  const [publish, setPublish] = useState(false);
  const [updateExisting, setUpdateExisting] = useState(true);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"" | "preview" | "import">("");
  const fileInput = useRef<HTMLInputElement>(null);
  const { push } = useToast();

  useEffect(() => {
    apiFetch<ImporterInfo[]>("/imports/sources").then(setSources, (e) => setError(e.message));
  }, []);

  const info = sources.find((s) => s.key === source);

  function formData() {
    const fd = new FormData();
    fd.append("source", source);
    if (file) fd.append("file", file);
    return fd;
  }

  async function onPreview() {
    if (!file) return setError("Choose a file first.");
    setBusy("preview");
    setError("");
    setSummary(null);
    try {
      setPreview(await apiFetch<ImportPreview>("/imports/preview", { method: "POST", body: formData() }));
    } catch (e) {
      setPreview(null);
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setBusy("");
    }
  }

  async function onImport() {
    if (!file) return setError("Choose a file first.");
    setBusy("import");
    setError("");
    const fd = formData();
    if (categoryId) fd.append("category_id", categoryId);
    fd.append("publish", String(publish));
    fd.append("update_existing", String(updateExisting));
    try {
      const done = await apiFetch<ImportSummary>("/imports", { method: "POST", body: fd });
      setSummary(done);
      setPreview(null);
      push({ title: "Import finished", description: `${done.created} created, ${done.updated} updated` });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy("");
    }
  }

  async function download(path: string, name: string) {
    try {
      await downloadFile(path, name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    }
  }

  const previewColumns: Column<ImportPreview["rows"][number]>[] = [
    { key: "row", header: "Row", cell: (r) => <span className="num text-muted">{r.row}</span> },
    {
      key: "title",
      header: "Title",
      cell: (r) => (
        <>
          <span className="block max-w-[22rem] truncate">{r.title}</span>
          {r.category && <span className="block text-xs text-muted">{r.category}</span>}
        </>
      ),
    },
    { key: "sku", header: "SKU", hide: "sm", cell: (r) => <span className="font-mono text-xs">{r.sku ?? "—"}</span> },
    { key: "price", header: "Price", align: "right", cell: (r) => <span className="num">{formatPrice(r.price)}</span> },
    { key: "qty", header: "Qty", align: "right", hide: "sm", cell: (r) => <span className="num">{r.quantity ?? "—"}</span> },
    { key: "images", header: "Images", align: "right", hide: "md", cell: (r) => <span className="num">{r.images}</span> },
    { key: "variants", header: "Variants", align: "right", hide: "md", cell: (r) => <span className="num">{r.variants || "—"}</span> },
    {
      key: "attrs",
      header: "Details",
      hide: "lg",
      cell: (r) => (
        <span className="block max-w-[20rem] truncate text-xs text-muted">
          {Object.entries(r.attributes)
            .map(([k, v]) => `${k}: ${formatAttribute(v)}`)
            .join("; ") || "—"}
        </span>
      ),
    },
  ];

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Import and export"
        description="Bring in listings from Etsy, Amazon or a spreadsheet. Re-importing the same file updates products instead of duplicating them."
      />

      <Panel aria-label="Import products">
        <PanelHeader title="Import products" />
        <PanelBody>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Source">
            {(p) => (
              <Select
                {...p}
                value={source}
                onChange={(e) => {
                  setSource(e.target.value);
                  setPreview(null);
                  setSummary(null);
                }}
              >
                {sources.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="File" hint={info ? `Accepted: ${info.accepted_extensions.join(", ")}` : undefined}>
            {(p) => (
              <input
                {...p}
                ref={fileInput}
                type="file"
                accept={info?.accepted_extensions.join(",")}
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  setPreview(null);
                  setSummary(null);
                }}
                className="block w-full text-sm file:mr-3 file:rounded-[var(--radius-control)] file:border-0 file:bg-sand file:px-3 file:py-1.5 file:text-sm file:font-medium"
              />
            )}
          </Field>
        </div>
        {HOW_TO[source] && <p className="mt-3 text-sm text-muted">{HOW_TO[source]}</p>}

        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <Field label="Category for rows without one" hint="Optional.">
            {(p) => (
              <Select {...p} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                <option value="">— None —</option>
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="space-y-3 pt-7 text-sm">
            <label className="flex items-center gap-2.5">
              <input type="checkbox" checked={updateExisting} onChange={(e) => setUpdateExisting(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
              Update products that were already imported
            </label>
            {can("catalog:publish") ? (
              <label className="flex items-center gap-2.5">
                <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
                Publish immediately (otherwise imported as drafts)
              </label>
            ) : (
              <p className="text-muted">Imported products are saved as drafts for a publisher to review.</p>
            )}
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Button variant="secondary" size="sm" className="h-9" onClick={onPreview} disabled={!file || !!busy}>
            {busy === "preview" ? "Reading file…" : "Preview"}
          </Button>
          <Button size="sm" className="h-9" onClick={onImport} disabled={!file || !!busy}>
            {busy === "import" ? "Importing…" : "Import"}
          </Button>
        </div>

        <div aria-live="polite" className="mt-6 space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}

          {summary && (
            <Alert tone={summary.errors.length ? "info" : "success"}>
              <p className="font-medium">
                Import finished: {summary.created} created, {summary.updated} updated, {summary.skipped} skipped
                {summary.variants ? `, ${summary.variants} variants` : ""}.
              </p>
              {summary.errors.length > 0 && (
                <ul className="mt-2 list-disc pl-5">
                  {summary.errors.slice(0, 20).map((e) => (
                    <li key={`${e.row}-${e.error}`}>
                      Row {e.row} {e.title ? `(${e.title})` : ""}: {e.error}
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2">
                <Link href="/admin/products?status=draft" className="underline">
                  Review imported products
                </Link>
              </p>
            </Alert>
          )}
          {(preview?.warnings.length || summary?.warnings.length) ? (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted">
                {(preview?.warnings ?? summary?.warnings ?? []).length} warnings
              </summary>
              <ul className="mt-2 list-disc pl-5 text-muted">
                {(preview?.warnings ?? summary?.warnings ?? []).map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>

        {preview && (
          <div className="mt-4">
            <p className="text-sm">
              Found <strong>{preview.total}</strong> products
              {preview.total > preview.rows.length ? ` (showing first ${preview.rows.length})` : ""}. Nothing has been saved yet.
            </p>
            <div className="mt-3 max-h-[28rem] overflow-auto rounded-[var(--radius-card)] border border-line">
              <DataTable caption="Import preview" columns={previewColumns} rows={preview.rows} rowKey={(r) => r.row} />
            </div>
          </div>
        )}
        </PanelBody>
      </Panel>

      <Panel aria-label="Manage in Excel" className="mt-6">
        <PanelHeader title="Manage in Excel" description="Download the catalog, edit prices, stock or descriptions, then import the file back with source “Spreadsheet”. Products are matched by SKU." />
        <PanelBody className="flex flex-wrap gap-3">
          <Button variant="secondary" size="sm" className="h-9" onClick={() => download("/products/export.xlsx", "wcw-catalog.xlsx")}>
            <Icon name="download" className="size-4" />
            Export catalog (.xlsx)
          </Button>
          <Button variant="ghost" size="sm" className="h-9" onClick={() => download("/imports/template.xlsx", "wcw-import-template.xlsx")}>
            Download blank template
          </Button>
        </PanelBody>
      </Panel>
    </div>
  );
}
