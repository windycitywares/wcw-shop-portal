import Link from "next/link";
import { fmt } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { cn } from "@/lib/utils";

/** Page numbers to show: always the first and last, the current page with its neighbours, "…" for the gaps. */
export function pageItems(page: number, pages: number): (number | "gap")[] {
  const wanted = new Set([1, pages, page - 1, page, page + 1]);
  if (page <= 3) [2, 3, 4].forEach((n) => wanted.add(n));
  if (page >= pages - 2) [pages - 1, pages - 2, pages - 3].forEach((n) => wanted.add(n));
  const nums = [...wanted].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
  const out: (number | "gap")[] = [];
  nums.forEach((n, i) => {
    if (i > 0 && n - nums[i - 1] > 1) out.push("gap");
    out.push(n);
  });
  return out;
}

const arrow = "inline-flex h-10 min-w-10 items-center justify-center gap-1 rounded-full border border-line bg-surface px-3 text-sm hover:border-ink/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

function Chevron({ dir }: { dir: "left" | "right" }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d={dir === "left" ? "M12 4 6 10l6 6" : "m8 4 6 6-6 6"} />
    </svg>
  );
}

export function Pager({ page, pages, href, t }: { page: number; pages: number; href: (page: number) => string; t: Dictionary }) {
  return (
    <nav aria-label={t.listing.pagination} className="mt-16 flex flex-wrap items-center justify-center gap-2 text-sm">
      {page > 1 ? (
        <Link href={href(page - 1)} rel="prev" className={arrow}>
          <Chevron dir="left" />
          <span className="hidden sm:inline">{t.listing.previous}</span>
          <span className="sr-only sm:hidden">{t.listing.previous}</span>
        </Link>
      ) : (
        <span aria-hidden="true" className={cn(arrow, "pointer-events-none opacity-40")}>
          <Chevron dir="left" />
          <span className="hidden sm:inline">{t.listing.previous}</span>
        </span>
      )}
      {/* Small screens: "Page 3 of 9" (numbers would wrap); wider screens: the numbered pages. */}
      <span className="px-3 text-muted sm:hidden">{fmt(t.listing.pageOf, { page, pages })}</span>
      <ol className="hidden items-center gap-1 sm:flex">
        {pageItems(page, pages).map((item, i) =>
          item === "gap" ? (
            <li key={`gap-${i}`} aria-hidden="true" className="px-1 text-muted">
              …
            </li>
          ) : (
            <li key={item}>
              <Link
                href={href(item)}
                aria-label={fmt(t.listing.goToPage, { page: item })}
                aria-current={item === page ? "page" : undefined}
                className={cn(
                  "inline-flex h-10 min-w-10 items-center justify-center rounded-full px-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink",
                  item === page ? "bg-ink text-canvas" : "hover:bg-sand/70",
                )}
              >
                {item}
              </Link>
            </li>
          ),
        )}
      </ol>
      {page < pages ? (
        <Link href={href(page + 1)} rel="next" className={arrow}>
          <span className="hidden sm:inline">{t.listing.next}</span>
          <span className="sr-only sm:hidden">{t.listing.next}</span>
          <Chevron dir="right" />
        </Link>
      ) : (
        <span aria-hidden="true" className={cn(arrow, "pointer-events-none opacity-40")}>
          <span className="hidden sm:inline">{t.listing.next}</span>
          <Chevron dir="right" />
        </span>
      )}
    </nav>
  );
}
