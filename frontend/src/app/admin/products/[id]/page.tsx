"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import type { ContentStatus, ProductDetail, StockStatus } from "@/lib/types";
import { STATUS_LABEL, STOCK_LABEL, formatPrice } from "@/lib/utils";
import { AttributeBuilder, fromRows, toRows, type AttributeRow } from "@/components/admin/AttributeBuilder";
import { useCategoryTree } from "@/components/admin/useCategoryOptions";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Alert, Badge } from "@/components/ui/misc";

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
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

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
    setNotice("");
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
        router.replace(`/admin/products/${created.id}`);
      } else {
        const updated = await apiFetch<ProductDetail>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(body) });
        setProduct(updated);
        setForm(fromProduct(updated));
        setNotice("Saved.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!product) return;
    if (!window.confirm(`Delete “${product.title}”${product.variants.length ? " and its variants" : ""}? This can't be undone.`)) return;
    try {
      await apiFetch(`/products/${product.id}`, { method: "DELETE" });
      router.replace("/admin/products");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="max-w-3xl">
      <Link href="/admin/products" className="text-sm text-muted hover:text-ink">
        ← All products
      </Link>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="text-4xl">{isNew ? (parentId ? "New variant" : "New product") : form.title || "Product"}</h1>
        {product && <Badge>{STATUS_LABEL[product.status]}</Badge>}
      </div>
      {product?.status === "published" && (
        <Link href={`/product/${product.slug}`} className="mt-2 inline-block text-sm text-accent underline">
          View in shop
        </Link>
      )}

      <form onSubmit={onSubmit} className="mt-8 space-y-6">
        {error && <Alert tone="danger">{error}</Alert>}
        {notice && <Alert tone="success">{notice}</Alert>}

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Title" className="sm:col-span-2">
            {(p) => <Input {...p} required value={form.title} onChange={set("title")} />}
          </Field>
          <Field label="SKU">{(p) => <Input {...p} required value={form.sku} onChange={set("sku")} />}</Field>
          <Field label="URL slug" hint="Leave blank to generate from the title.">
            {(p) => <Input {...p} value={form.slug} onChange={set("slug")} pattern="[a-z0-9]+(-[a-z0-9]+)*" />}
          </Field>
          <Field label="Price (USD)">
            {(p) => <Input {...p} required type="number" min={0} step="0.01" value={form.base_price} onChange={set("base_price")} />}
          </Field>
          <Field label="Compare-at price" hint="Original price, to show a sale.">
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
          <Field label="Status" hint={can("catalog:publish") ? undefined : "A publisher will review and publish it."}>
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

        <Field label="Description">
          {(p) => <Textarea {...p} rows={6} value={form.description} onChange={set("description")} />}
        </Field>
        <Field label="Image URLs" hint="One per line. The first image is the main photo.">
          {(p) => <Textarea {...p} rows={4} value={form.images} onChange={set("images")} className="font-mono text-xs" />}
        </Field>
        <Field label="Tags" hint="Comma separated.">
          {(p) => <Input {...p} value={form.tags} onChange={set("tags")} />}
        </Field>

        <AttributeBuilder rows={attrs} onChange={setAttrs} />

        <details className="rounded-lg border border-line p-4">
          <summary className="cursor-pointer text-sm font-medium">Search engine listing</summary>
          <div className="mt-4 space-y-4">
            <Field label="SEO title">{(p) => <Input {...p} maxLength={300} value={form.seo_title} onChange={set("seo_title")} />}</Field>
            <Field label="SEO description" hint="About 150 characters.">
              {(p) => <Textarea {...p} maxLength={500} value={form.seo_description} onChange={set("seo_description")} />}
            </Field>
          </div>
        </details>

        <div className="flex flex-wrap items-center gap-3 border-t border-line pt-6">
          <Button type="submit" disabled={busy}>
            {busy ? "Saving…" : isNew ? "Create product" : "Save changes"}
          </Button>
          {product && can("catalog:delete") && (
            <Button variant="danger" onClick={onDelete}>
              Delete
            </Button>
          )}
        </div>
      </form>

      {product && product.parent_id === null && (
        <section aria-labelledby="variants-heading" className="mt-12">
          <div className="flex items-center justify-between">
            <h2 id="variants-heading" className="text-2xl">
              Variants
            </h2>
            {can("catalog:create") && (
              <Link href={`/admin/products/new?parent=${product.id}`} className="text-sm text-accent underline">
                Add variant
              </Link>
            )}
          </div>
          {product.variants.length === 0 ? (
            <p className="mt-3 text-sm text-muted">
              No variants. Add one for each option with its own SKU or price (e.g. Large / Walnut).
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-line rounded-lg border border-line bg-surface">
              {product.variants.map((v) => (
                <li key={v.id} className="flex items-center justify-between px-4 py-3 text-sm">
                  <Link href={`/admin/products/${v.id}`} className="hover:underline">
                    {v.title} <span className="font-mono text-xs text-muted">{v.sku}</span>
                  </Link>
                  <span>{formatPrice(v.base_price, v.currency)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
