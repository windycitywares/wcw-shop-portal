"use client";

import { Heart } from "@untitledui/icons";
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
      <Heart aria-hidden="true" className="size-5" strokeWidth={1.6} />
      <span className="sr-only">{t.wishlist.title}</span>
    </Link>
  );
}
