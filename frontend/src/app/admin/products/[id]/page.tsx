"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import type { ContentStatus, ProductDetail, StockStatus } from "@/lib/types";
import { STATUS_LABEL, STOCK_LABEL, formatPrice } from "@/lib/utils";
import { AttributeBuilder, fromRows, toRows, type AttributeRow } from "@/components/admin/AttributeBuilder";
import { PhotoManager } from "@/components/admin/PhotoManager";
import { useCategoryTree } from "@/components/admin/useCategoryOptions";
import { Icon } from "@/components/admin/ui/Icon";
import { ConfirmDialog } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

const STATUS_TONE: Record<ContentStatus, Tone> = { draft: "neutral", in_review: "accent", published: "success", archived: "warning" };

interface FormState {
  title: string;
  sku: string;
  slug: string;
  description: string;
  base_price: string;
  compare_at_price: string;
  stock_status: StockStatus;
  stock_quantity: string;
  category_id: string;
  tags: string;
  images: string;
  status: ContentStatus;
  seo_title: string;
  seo_description: string;
}

const EMPTY: FormState = {
  title: "",
  sku: "",
  slug: "",
  description: "",
  base_price: "",
  compare_at_price: "",
  stock_status: "in_stock",
  stock_quantity: "",
  category_id: "",
  tags: "",
  images: "",
  status: "draft",
  seo_title: "",
  seo_description: "",
};

function fromProduct(p: ProductDetail): FormState {
  return {
    title: p.title,
    sku: p.sku,
    slug: p.slug,
    description: p.description ?? "",
    base_price: String(p.base_price),
    compare_at_price: p.compare_at_price != null ? String(p.compare_at_price) : "",
    stock_status: p.stock_status,
    stock_quantity: p.stock_quantity != null ? String(p.stock_quantity) : "",
    category_id: p.category_id != null ? String(p.category_id) : "",
    tags: p.tags.join(", "),
    images: p.images.map((i) => i.url).join("\n"),
    status: p.status,
    seo_title: p.seo_title ?? "",
    seo_description: p.seo_description ?? "",
  };
}

const orNull = (s: string) => (s.trim() === "" ? null : s.trim());
const numOrNull = (s: string) => (s.trim() === "" ? null : Number(s));

export default function ProductEditor() {
  const { id } = useParams<{ id: string }>();
  const isNew = id === "new";
  const router = useRouter();
  const { can } = useAuth();
  const { options } = useCategoryTree();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [attrs, setAttrs] = useState<AttributeRow[]>([]);
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [parentId, setParentId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { push } = useToast();

  useEffect(() => {
    if (isNew) {
      const parent = new URLSearchParams(window.location.search).get("parent");
      if (parent) setParentId(Number(parent));
      return;
    }
    apiFetch<ProductDetail>(`/products/by-id/${id}`).then(
      (p) => {
        setProduct(p);
        setForm(fromProduct(p));
        setAttrs(toRows(p.attributes));
      },
      (e) => setError(e.message),
    );
  }, [id, isNew]);

  const set = <K extends keyof FormState>(key: K) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value as FormState[K] }));

  const statusOptions: ContentStatus[] = can("catalog:publish")
    ? ["draft", "in_review", "published", "archived"]
    : ["draft", "in_review"];

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const body: Record<string, unknown> = {
      title: form.title.trim(),
      sku: form.sku.trim(),
      description: orNull(form.description),
      base_price: Number(form.base_price || 0),
      compare_at_price: numOrNull(form.compare_at_price),
      stock_status: form.stock_status,
      stock_quantity: numOrNull(form.stock_quantity),
      category_id: numOrNull(form.category_id),
      tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
      images: form.images
        .split("\n")
        .map((u) => u.trim())
        .filter(Boolean)
        .map((url) => ({ url, alt: form.title.trim() })),
      attributes: fromRows(attrs),
      seo_title: orNull(form.seo_title),
      seo_description: orNull(form.seo_description),
    };
    if (form.slug.trim()) body.slug = form.slug.trim();
    if (isNew || form.status !== product?.status) body.status = form.status;
    if (isNew && parentId) body.parent_id = parentId;

    try {
      if (isNew) {
        const created = await apiFetch<ProductDetail>("/products", { method: "POST", body: JSON.stringify(body) });
        push({ title: "Product created", description: created.title });
        router.replace(`/admin/products/${created.id}`);
      } else {
        const updated = await apiFetch<ProductDetail>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(body) });
        setProduct(updated);
        setForm(fromProduct(updated));
        push({ title: "Saved", description: updated.title });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!product) return;
    setConfirmDelete(false);
    try {
      await apiFetch(`/products/${product.id}`, { method: "DELETE" });
      push({ title: "Deleted", description: product.title });
      router.replace("/admin/products");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  const imageUrls = form.images.split("\n").map((u) => u.trim()).filter(Boolean);
  const onSale = form.compare_at_price !== "" && Number(form.compare_at_price) > Number(form.base_price || 0);
  const title = isNew ? (parentId ? "New variant" : "New product") : form.title || "Product";

  return (
    <div>
      <PageHeader
        back={{ href: "/admin/products", label: "All products" }}
        title={title}
        description={
          product ? (
            <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
              <Pill tone={STATUS_TONE[product.status]}>{STATUS_LABEL[product.status]}</Pill>
              <span className="font-mono text-xs">{product.sku}</span>
              {product.status === "published" && (
                <Link href={`/product/${product.slug}`} className="inline-flex items-center gap-1 text-accent underline">
                  View in shop
                  <Icon name="external" className="size-3.5" />
                </Link>
              )}
            </span>
          ) : undefined
        }
        actions={
          <>
            {product && can("catalog:delete") && (
              <Button variant="ghost" size="sm" className="h-9 text-danger hover:bg-danger/10" onClick={() => setConfirmDelete(true)}>
                <Icon name="trash" className="size-4" />
                Delete
              </Button>
            )}
            <Button type="submit" form="product-form" size="sm" className="h-9" disabled={busy}>
              {busy ? "Saving…" : isNew ? "Create product" : "Save changes"}
            </Button>
          </>
        }
      />

      <form id="product-form" onSubmit={onSubmit} className="grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]">
        {error && (
          <Alert tone="danger" className="lg:col-span-2">
            {error}
          </Alert>
        )}

        <div className="min-w-0 space-y-6">
          <Panel>
            <PanelHeader title="Listing" />
            <div className="space-y-5 p-5">
              <Field label="Title">{(p) => <Input {...p} required value={form.title} onChange={set("title")} />}</Field>
              <Field label="Description" hint="Plain text. Say what it is, what it is made of and how big it is.">
                {(p) => <Textarea {...p} rows={8} value={form.description} onChange={set("description")} />}
              </Field>
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Photos" description="The first photo is the main one in the shop. Use the arrows to change the order, then save." />
            <div className="p-5">
              <PhotoManager
                productId={product?.id ?? null}
                urls={imageUrls}
                onChange={(next) => setForm((f) => ({ ...f, images: next.join("\n") }))}
                onSaved={(saved) => {
                  setProduct(saved);
                  // Keep unsaved edits to other fields; take the photo list as the server saved it.
                  setForm((f) => ({ ...f, images: saved.images.map((i) => i.url).join("\n") }));
                }}
              />
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Details and options" description="Size, material and similar facts. Lists such as Red, Blue become choices on the product page." />
            <div className="space-y-5 p-5">
              <AttributeBuilder rows={attrs} onChange={setAttrs} />
              <Field label="Tags" hint="Comma separated. Used for search and related products.">
                {(p) => <Input {...p} value={form.tags} onChange={set("tags")} />}
              </Field>
            </div>
          </Panel>

          <Panel>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4">
                <span>
                  <span className="block text-base font-semibold">Search engine listing</span>
                  <span className="block text-sm text-muted">How this product appears in Google. Leave blank to use the title and description.</span>
                </span>
                <Icon name="chevronDown" className="size-4 text-muted transition-transform group-open:rotate-180" />
              </summary>
              <div className="space-y-4 border-t border-line p-5">
                <Field label="SEO title">{(p) => <Input {...p} maxLength={300} value={form.seo_title} onChange={set("seo_title")} />}</Field>
                <Field label="SEO description" hint="About 150 characters.">
                  {(p) => <Textarea {...p} maxLength={500} value={form.seo_description} onChange={set("seo_description")} />}
                </Field>
              </div>
            </details>
          </Panel>
        </div>

        <aside className="space-y-6 lg:sticky lg:top-20">
          <Panel>
            <PanelHeader title="Status" />
            <div className="p-5">
              <Field label="Visibility" hint={can("catalog:publish") ? "Only published products appear in the shop." : "A publisher will review and publish it."}>
                {(p) => (
                  <Select {...p} value={form.status} onChange={set("status")}>
                    {statusOptions.map((s) => (
                      <option key={s} value={s}>
                        {STATUS_LABEL[s]}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Price and stock" />
            <div className="grid gap-4 p-5">
              <Field label="Price (USD)">
                {(p) => <Input {...p} required type="number" min={0} step="0.01" value={form.base_price} onChange={set("base_price")} />}
              </Field>
              <Field
                label="Compare-at price"
                hint={onSale ? `Shown as a sale: ${Math.round((1 - Number(form.base_price || 0) / Number(form.compare_at_price)) * 100)}% off.` : "The original price. Fill in to show a sale."}
              >
                {(p) => <Input {...p} type="number" min={0} step="0.01" value={form.compare_at_price} onChange={set("compare_at_price")} />}
              </Field>
              <Field label="Stock status">
                {(p) => (
                  <Select {...p} value={form.stock_status} onChange={set("stock_status")}>
                    {Object.entries(STOCK_LABEL).map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Quantity">
                {(p) => <Input {...p} type="number" min={0} value={form.stock_quantity} onChange={set("stock_quantity")} />}
              </Field>
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Organise" />
            <div className="grid gap-4 p-5">
              <Field label="Category">
                {(p) => (
                  <Select {...p} value={form.category_id} onChange={set("category_id")}>
                    <option value="">— None —</option>
                    {options.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="SKU">{(p) => <Input {...p} required value={form.sku} onChange={set("sku")} />}</Field>
              <Field label="URL slug" hint="Leave blank to generate from the title.">
                {(p) => <Input {...p} value={form.slug} onChange={set("slug")} pattern="[a-z0-9]+(-[a-z0-9]+)*" />}
              </Field>
            </div>
          </Panel>
        </aside>
      </form>

      {product && product.parent_id === null && (
        <Panel aria-label="Variants" className="mt-6">
          <PanelHeader
            title="Variants"
            description="Separate SKUs or prices for each option, such as Large in Walnut."
            actions={
              can("catalog:create") ? (
                <Link href={`/admin/products/new?parent=${product.id}`} className="inline-flex h-8 items-center gap-1 rounded-[var(--radius-control)] border border-line px-2.5 text-sm font-medium hover:border-ink/40">
                  <Icon name="plus" className="size-4" />
                  Add variant
                </Link>
              ) : undefined
            }
          />
          {product.variants.length === 0 ? (
            <p className="px-5 py-6 text-sm text-muted">No variants yet.</p>
          ) : (
            <ul className="divide-y divide-line">
              {product.variants.map((v) => (
                <li key={v.id} className="flex items-center justify-between px-5 py-3 text-sm">
                  <Link href={`/admin/products/${v.id}`} className="hover:underline">
                    {v.title} <span className="font-mono text-xs text-muted">{v.sku}</span>
                  </Link>
                  <span className="num">{formatPrice(v.base_price, v.currency)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title={`Delete “${product?.title ?? ""}”?`}
        message={product?.variants.length ? "Its variants will be deleted too. This can't be undone." : "This can't be undone."}
        confirmLabel="Delete product"
        onCancel={() => setConfirmDelete(false)}
        onConfirm={onDelete}
      />
    </div>
  );
}
