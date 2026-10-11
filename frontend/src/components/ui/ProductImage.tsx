import Image from "next/image";
import { cn } from "@/lib/utils";

// Hosts listed in next.config.ts images.remotePatterns get optimized; any
// other host (e.g. a URL from an imported spreadsheet) is shown as-is.
const OPTIMIZED_HOSTS = new Set(["i.etsystatic.com", "m.media-amazon.com", "images-na.ssl-images-amazon.com"]);

function canOptimize(src: string) {
  try {
    return OPTIMIZED_HOSTS.has(new URL(src).hostname);
  } catch {
    return src.startsWith("/");
  }
}

export function ProductImage({
  src,
  alt,
  sizes,
  priority,
  className,
}: {
  src?: string | null;
  alt: string;
  sizes: string;
  priority?: boolean;
  className?: string;
}) {
  const url = src || "/placeholder.svg";
  return (
    <Image
      src={url}
      alt={src ? alt : ""}
      fill
      sizes={sizes}
      priority={priority}
      unoptimized={!canOptimize(url) || url.endsWith(".svg")}
      className={cn("object-cover", className)}
    />
  );
}
