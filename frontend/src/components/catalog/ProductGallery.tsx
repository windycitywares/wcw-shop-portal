"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "@/i18n/client";
import type { Product, ProductImage as Img } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ProductImage } from "@/components/ui/ProductImage";
import { useProductView } from "@/components/catalog/ProductView";

const arrowBtn =
  "absolute top-1/2 z-10 grid size-10 -translate-y-1/2 place-items-center rounded-full bg-canvas/90 text-ink shadow hover:bg-canvas focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

function Arrow({ dir, onClick, label }: { dir: "prev" | "next"; onClick: () => void; label: string }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} className={cn(arrowBtn, dir === "prev" ? "left-3" : "right-3")}>
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d={dir === "prev" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"} />
      </svg>
    </button>
  );
}

export function ProductGallery({ images, variants = [], title }: { images: Img[]; variants?: Product[]; title: string }) {
  const { t, fmt } = useI18n();
  const { variantId } = useProductView();
  // Every picture of the product and of its variations, once each.
  const all = useMemo(() => {
    const seen = new Set<string>();
    return [...images, ...variants.flatMap((v) => v.images ?? [])].filter((i) => !seen.has(i.url) && seen.add(i.url));
  }, [images, variants]);
  const [index, setIndex] = useState(0);
  const [zoom, setZoom] = useState(false);
  const [big, setBig] = useState(false); // magnified inside the viewer
  const n = all.length;
  const go = useCallback((d: number) => { setIndex((i) => (i + d + n) % n); setBig(false); }, [n]);

  // Choosing a variation brings its first picture up.
  const firstOfVariant = variants.find((v) => v.id === variantId)?.images?.[0]?.url;
  useEffect(() => {
    if (!firstOfVariant) return;
    const i = all.findIndex((x) => x.url === firstOfVariant);
    if (i >= 0) setIndex(i);
  }, [firstOfVariant, all]);

  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!zoom) return;
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setZoom(false);
      else if (n > 1 && e.key === "ArrowLeft") go(-1);
      else if (n > 1 && e.key === "ArrowRight") go(1);
    };
    document.addEventListener("keydown", key);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = prev; };
  }, [zoom, go, n]);

  const current = all[index];
  const onKey = (e: React.KeyboardEvent) => {
    if (n < 2) return;
    if (e.key === "ArrowLeft") go(-1);
    if (e.key === "ArrowRight") go(1);
  };
  return (
    <div className="lg:sticky lg:top-28" onKeyDown={onKey}>
      <div className="mat">
        <div className="relative aspect-[4/5] overflow-hidden bg-sand">
          <ProductImage src={current?.url} alt={current?.alt || title} sizes="(min-width: 1024px) 50vw, 100vw" priority />
          <button
            type="button"
            onClick={() => setZoom(true)}
            aria-label={t.product.zoomImage}
            className="absolute inset-0 cursor-zoom-in focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
          />
          {n > 1 && (
            <>
              <Arrow dir="prev" onClick={() => go(-1)} label={t.product.prevImage} />
              <Arrow dir="next" onClick={() => go(1)} label={t.product.nextImage} />
            </>
          )}
        </div>
      </div>
      {n > 1 && (
        <ul className="mt-4 grid grid-cols-6 gap-2 sm:gap-3" aria-label={t.product.images}>
          {all.map((img, i) => (
            <li key={img.url}>
              <button
                type="button"
                onClick={() => setIndex(i)}
                aria-current={i === index}
                className={cn(
                  "relative block aspect-square w-full overflow-hidden rounded-[2px] bg-sand outline-offset-2",
                  i === index ? "ring-1 ring-ink ring-offset-2 ring-offset-canvas" : "opacity-70 hover:opacity-100",
                )}
              >
                <ProductImage src={img.url} alt="" sizes="96px" />
                <span className="sr-only">{fmt(t.product.showImage, { index: i + 1, total: n })}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {zoom && (
        <div role="dialog" aria-modal="true" aria-label={t.product.images} className="fixed inset-0 z-50 flex items-center justify-center bg-ink/90 p-4">
          <button ref={closeRef} type="button" onClick={() => setZoom(false)} aria-label={t.product.closeZoom}
            className="absolute right-4 top-4 z-10 grid size-10 place-items-center rounded-full bg-canvas text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
            <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
          <div className={cn("relative h-full w-full max-w-5xl overflow-auto", big && "cursor-zoom-out")}>
            <button type="button" onClick={() => setBig((b) => !b)} aria-label={t.product.zoomImage} aria-pressed={big}
              className={cn("relative block", big ? "h-[200%] w-[200%] cursor-zoom-out" : "h-full w-full cursor-zoom-in")}>
              <ProductImage src={current?.url} alt={current?.alt || title} sizes="100vw" className="object-contain" />
            </button>
          </div>
          {n > 1 && (
            <>
              <Arrow dir="prev" onClick={() => go(-1)} label={t.product.prevImage} />
              <Arrow dir="next" onClick={() => go(1)} label={t.product.nextImage} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
