"use client";

import { useState } from "react";
import type { ProductImage as Img } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ProductImage } from "@/components/ui/ProductImage";

export function ProductGallery({ images, title }: { images: Img[]; title: string }) {
  const [index, setIndex] = useState(0);
  const current = images[index];
  return (
    <div>
      <div className="relative aspect-[4/5] overflow-hidden rounded-[var(--radius-card)] bg-sand">
        <ProductImage
          src={current?.url}
          alt={current?.alt || title}
          sizes="(min-width: 1024px) 50vw, 100vw"
          priority
        />
      </div>
      {images.length > 1 && (
        <ul className="mt-4 grid grid-cols-5 gap-3" aria-label="Product images">
          {images.map((img, i) => (
            <li key={img.url}>
              <button
                type="button"
                onClick={() => setIndex(i)}
                aria-current={i === index}
                className={cn(
                  "relative block aspect-square w-full overflow-hidden rounded-lg bg-sand ring-offset-2 ring-offset-canvas",
                  i === index ? "ring-2 ring-accent" : "opacity-80 hover:opacity-100",
                )}
              >
                <ProductImage src={img.url} alt="" sizes="96px" />
                <span className="sr-only">{`Show image ${i + 1} of ${images.length}`}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
