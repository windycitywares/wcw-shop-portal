"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { useAuth } from "@/lib/auth";
import { wishlistApi } from "@/lib/engagement";
import { cn } from "@/lib/utils";

/** Heart toggle. Signed-out shoppers get a link to sign in (the wishlist lives in the account). */
export function WishlistButton({ productId, className }: { productId: number; className?: string }) {
  const { user } = useAuth();
  const { t, href } = useI18n();
  const pathname = usePathname();
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) wishlistApi.ids().then((ids) => setSaved(ids.has(productId)));
    else setSaved(false);
  }, [user, productId]);

  const heart = (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-5" fill={saved ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.6">
      <path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.6 4.5 7.1 4.5c2 0 3.4 1.1 4.9 2.9 1.5-1.8 2.9-2.9 4.9-2.9 3.5 0 5.7 3.5 4.4 6.8-1.8 4.6-9.3 9.2-9.3 9.2z" />
    </svg>
  );
  const base = cn(
    "inline-flex h-11 items-center gap-2 rounded-[var(--radius-control)] border border-line bg-surface px-4 text-sm hover:border-ink/40",
    saved && "text-sale",
    className,
  );

  if (!user) {
    return (
      <Link href={`${href("/login")}?next=${encodeURIComponent(pathname)}`} className={base}>
        {heart}
        <span>{t.wishlist.signIn}</span>
      </Link>
    );
  }
  return (
    <button
      type="button"
      aria-pressed={saved}
      disabled={busy}
      className={base}
      onClick={async () => {
        setBusy(true);
        try {
          if (saved) await wishlistApi.remove(productId);
          else await wishlistApi.add(productId);
          setSaved(!saved);
        } finally {
          setBusy(false);
        }
      }}
    >
      {heart}
      <span>{saved ? t.wishlist.remove : t.wishlist.add}</span>
    </button>
  );
}
