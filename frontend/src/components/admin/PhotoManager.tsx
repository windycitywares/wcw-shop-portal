"use client";

import { useRef, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { ProductDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/admin/ui/Icon";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ProductImage } from "@/components/ui/ProductImage";

const ACCEPT = "image/jpeg,image/png,image/webp";
const MAX_FILES = 10;

/**
 * Product photos: upload (named after the product by the API), drag-free reordering with buttons, remove, and
 * adding an image by address. Order changes are part of the product form and saved with "Save changes";
 * uploads and removals are saved straight away.
 */
export function PhotoManager({
  productId,
  urls,
  onChange,
  onSaved,
}: {
  /** null for a product that hasn't been created yet: uploading needs a product to name the files after. */
  productId: number | null;
  urls: string[];
  onChange: (urls: string[]) => void;
  /** Called with the product as saved after an upload or removal. */
  onSaved: (product: ProductDetail) => void;
}) {
  const { push } = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [link, setLink] = useState("");

  async function upload(files: File[]) {
    if (!productId || files.length === 0) return;
    if (files.length > MAX_FILES) {
      push({ title: `Upload up to ${MAX_FILES} photos at a time`, tone: "danger" });
      return;
    }
    const body = new FormData();
    files.forEach((f) => body.append("files", f));
    setBusy(true);
    try {
      const saved = await apiFetch<ProductDetail>(`/products/${productId}/photos`, { method: "POST", body });
      onSaved(saved);
      push({ title: files.length === 1 ? "Photo uploaded" : `${files.length} photos uploaded`, description: "Named after the product." });
    } catch (e) {
      push({ title: "Upload failed", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function remove(url: string) {
    if (!productId) {
      onChange(urls.filter((u) => u !== url));
      return;
    }
    setBusy(true);
    try {
      onSaved(await apiFetch<ProductDetail>(`/products/${productId}/photos?url=${encodeURIComponent(url)}`, { method: "DELETE" }));
      push({ title: "Photo removed" });
    } catch (e) {
      push({ title: "Couldn't remove the photo", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  function move(i: number, to: number) {
    const next = [...urls];
    const [item] = next.splice(i, 1);
    next.splice(to, 0, item);
    onChange(next);
  }

  function addLink() {
    const url = link.trim();
    if (!/^https?:\/\/\S+$/i.test(url)) {
      push({ title: "Enter a full image address starting with https://", tone: "danger" });
      return;
    }
    if (!urls.includes(url)) onChange([...urls, url]);
    setLink("");
  }

  return (
    <div className="space-y-4">
      {urls.length > 0 && (
        <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4" aria-label="Photos, in the order shown in the shop">
          {urls.map((u, i) => (
            <li key={`${u}-${i}`} className="overflow-hidden rounded-[var(--radius-control)] border border-line bg-surface">
              <div className={cn("relative aspect-square bg-sand", i === 0 && "ring-2 ring-inset ring-accent")}>
                <ProductImage src={u} alt={`Photo ${i + 1}`} sizes="160px" />
                {i === 0 && <span className="absolute left-1.5 top-1.5 rounded bg-accent px-1.5 py-0.5 text-xs font-medium text-on-accent">Main</span>}
              </div>
              <div className="flex items-center justify-between gap-1 px-1.5 py-1">
                <span className="flex">
                  <button
                    type="button"
                    className="rounded p-1 text-muted hover:text-ink disabled:opacity-30"
                    disabled={busy || i === 0}
                    onClick={() => move(i, i - 1)}
                    aria-label={`Move photo ${i + 1} earlier`}
                  >
                    <Icon name="chevronLeft" className="size-4" />
                  </button>
                  <button
                    type="button"
                    className="rounded p-1 text-muted hover:text-ink disabled:opacity-30"
                    disabled={busy || i === urls.length - 1}
                    onClick={() => move(i, i + 1)}
                    aria-label={`Move photo ${i + 1} later`}
                  >
                    <Icon name="chevronRight" className="size-4" />
                  </button>
                </span>
                {i !== 0 && (
                  <button type="button" className="rounded px-1 text-xs text-muted hover:text-ink" disabled={busy} onClick={() => move(i, 0)}>
                    Make main
                    <span className="sr-only"> (photo {i + 1})</span>
                  </button>
                )}
                <button type="button" className="rounded p-1 text-muted hover:text-danger" disabled={busy} onClick={() => remove(u)} aria-label={`Remove photo ${i + 1}`}>
                  <Icon name="trash" className="size-4" />
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}

      <div
        className={cn(
          "relative rounded-[var(--radius-card)] border border-dashed border-line px-4 py-6 text-center transition-colors",
          dragging && "border-accent bg-accent-soft/40",
          !productId && "opacity-70",
        )}
        onDragOver={(e) => {
          if (!productId) return;
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload(Array.from(e.dataTransfer.files).filter((f) => ACCEPT.split(",").includes(f.type)));
        }}
      >
        <Icon name="import" className="mx-auto size-6 text-muted" />
        {productId ? (
          <>
            <p className="mt-2 text-sm">Drop photos here, or</p>
            <input
              ref={input}
              type="file"
              accept={ACCEPT}
              multiple
              aria-label="Upload photos"
              className="sr-only"
              tabIndex={-1}
              onChange={(e) => upload(Array.from(e.target.files ?? []))}
              disabled={busy}
            />
            <Button type="button" size="sm" variant="secondary" className="mt-2" disabled={busy} onClick={() => input.current?.click()}>
              {busy ? "Uploading…" : "Choose photos"}
            </Button>
            <p className="mt-2 text-xs text-muted">JPEG, PNG or WebP, up to 15 MB each. Files are named after the product, and location data is removed.</p>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted">Create the product first, then upload photos. They&apos;re named after it.</p>
        )}
      </div>

      <div className="flex gap-2">
        <label htmlFor="photo-link" className="sr-only">
          Add a photo by address
        </label>
        <Input
          id="photo-link"
          type="url"
          value={link}
          onChange={(e) => setLink(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addLink();
            }
          }}
          placeholder="Or paste an image address (https://…)"
          className="h-9"
        />
        <Button type="button" size="sm" variant="secondary" onClick={addLink}>
          Add
        </Button>
      </div>
    </div>
  );
}
