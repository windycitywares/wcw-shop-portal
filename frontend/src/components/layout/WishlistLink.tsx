"use client";

import Link from "next/link";
import { useI18n } from "@/i18n/client";
import { useAuth } from "@/lib/auth";

/** The saved-designs heart in the header. Signed-out shoppers are sent to sign in and come back to it. */
export function WishlistLink() {
  const { user } = useAuth();
  const { t, href } = useI18n();
  const wishlist = `${href("/account")}#my-wishlist`;
  const target = user ? wishlist : `${href("/login")}?next=${encodeURIComponent(wishlist)}`;
  return (
    <Link href={target} title={t.wishlist.title} className="grid size-10 place-items-center rounded-full hover:bg-sand">
      <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.6 4.5 7.1 4.5c2 0 3.4 1.1 4.9 2.9 1.5-1.8 2.9-2.9 4.9-2.9 3.5 0 5.7 3.5 4.4 6.8-1.8 4.6-9.3 9.2-9.3 9.2z" />
      </svg>
      <span className="sr-only">{t.wishlist.title}</span>
    </Link>
  );
}
