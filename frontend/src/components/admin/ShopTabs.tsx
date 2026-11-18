"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV, activeSection } from "@/components/admin/nav";
import { cn } from "@/lib/utils";

/** The sections of one external shop (Orders | Listings …), from its menu entry in nav.ts. */
export function ShopTabs({ shop }: { shop: string }) {
  const pathname = usePathname();
  const item = NAV.flatMap((g) => g.items).find((i) => i.channel === shop);
  if (!item?.sections) return null;
  const current = activeSection(item, pathname);
  return (
    <nav aria-label={`${item.label} sections`} className="flex gap-1 overflow-x-auto border-b border-line">
      {item.sections.map((s) => {
        const active = current?.href === s.href;
        return (
          <Link
            key={s.href}
            href={s.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "font-admin -mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold transition-colors",
              active ? "border-accent text-accent" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {s.label}
          </Link>
        );
      })}
    </nav>
  );
}
