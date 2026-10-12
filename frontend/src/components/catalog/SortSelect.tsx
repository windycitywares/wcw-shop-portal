"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useI18n } from "@/i18n/client";

const VALUES = ["newest", "price_asc", "price_desc", "title"] as const;

export function SortSelect() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { t } = useI18n();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("sort", e.target.value);
    params.delete("page");
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor="sort" className="text-muted">
        {t.listing.sortBy}
      </label>
      <select
        id="sort"
        value={searchParams.get("sort") || "newest"}
        onChange={onChange}
        className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3"
      >
        {VALUES.map((v) => (
          <option key={v} value={v}>
            {t.listing.sort[v]}
          </option>
        ))}
      </select>
    </div>
  );
}
