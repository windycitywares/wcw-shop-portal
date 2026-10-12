"use client";

import { useState } from "react";
import { useI18n } from "@/i18n/client";
import type { ProductImage as Img } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ProductImage } from "@/components/ui/ProductImage";

export function ProductGallery({ images, title }: { images: Img[]; title: string }) {
  const { t, fmt } = useI18n();
  const [index, setIndex] = useState(0);
  const current = images[index];
  return (
    <div className="lg:sticky lg:top-28">
      <div className="mat">
        <div className="relative aspect-[4/5] overflow-hidden bg-sand">
          <ProductImage src={current?.url} alt={current?.alt || title} sizes="(min-width: 1024px) 50vw, 100vw" priority />
        </div>
      </div>
      {images.length > 1 && (
        <ul className="mt-4 grid grid-cols-6 gap-2 sm:gap-3" aria-label={t.product.images}>
          {images.map((img, i) => (
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
                <span className="sr-only">{fmt(t.product.showImage, { index: i + 1, total: images.length })}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
