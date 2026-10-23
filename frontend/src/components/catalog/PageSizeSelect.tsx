"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useI18n } from "@/i18n/client";
import { PAGE_SIZES } from "./pageSizes";


/** "Show 24 per page": changing it goes back to page 1 and is kept in the address, so a shared link looks the same. */
export function PageSizeSelect({ value }: { value: number }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { t } = useI18n();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page_size", e.target.value);
    params.delete("page");
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor="page-size" className="text-muted">
        {t.listing.show}
      </label>
      <select id="page-size" value={value} onChange={onChange} className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3">
        {PAGE_SIZES.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
      <span className="text-muted">{t.listing.perPage}</span>
    </div>
  );
}
