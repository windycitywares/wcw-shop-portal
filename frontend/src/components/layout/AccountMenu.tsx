"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useI18n } from "@/i18n/client";
import { isStaff, useAuth } from "@/lib/auth";
import { Popover } from "@/components/ui/Popover";

const item = "flex items-center rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand";

/**
 * The top-right account spot: a plain "Sign in" link when signed out, and the person's name with a menu
 * (account, orders, wishlist, admin, sign out) when signed in.
 */
export function AccountMenu() {
  const { user, logout } = useAuth();
  const { t, href } = useI18n();
  const router = useRouter();

  if (!user) {
    return (
      <Link
        href={href("/login")}
        title={t.nav.signIn}
        className="grid size-10 place-items-center rounded-full hover:bg-sand"
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21a8 8 0 0 1 16 0" strokeLinecap="round" />
        </svg>
        <span className="sr-only">{t.nav.signIn}</span>
      </Link>
    );
  }

  const name = (user.full_name || "").trim() || user.email.split("@")[0];
  const first = name.split(/\s+/)[0];

  return (
    <Popover
      label={t.nav.accountMenu}
      title={t.nav.accountMenu}
      className="shrink-0"
      triggerClassName="h-10 max-w-44 gap-1.5 border-transparent bg-transparent px-2 hover:border-transparent hover:bg-sand"
      panelClassName="w-60"
      trigger={
        <>
          <span
            aria-hidden="true"
            className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-strong"
          >
            {first.slice(0, 1).toUpperCase()}
          </span>
          <span className="max-w-20 truncate text-sm font-medium sm:max-w-28">{first}</span>
          <svg aria-hidden="true" viewBox="0 0 24 24" className="size-3.5 shrink-0 text-muted" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </>
      }
    >
      {(close) => (
        <div>
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium">{name}</p>
            <p className="truncate text-xs text-muted">{user.email}</p>
          </div>
          <div className="border-t border-line pt-1">
            <Link href={href("/account")} onClick={close} className={item}>
              {t.nav.account}
            </Link>
            <Link href={`${href("/account")}#my-orders`} onClick={close} className={item}>
              {t.account.ordersTitle}
            </Link>
            <Link href={`${href("/account")}#my-wishlist`} onClick={close} className={item}>
              {t.wishlist.title}
            </Link>
            {isStaff(user) && (
              <Link href="/admin" onClick={close} className={item}>
                {t.nav.admin}
              </Link>
            )}
            <button
              type="button"
              onClick={() => {
                close();
                logout();
                router.push(href("/"));
              }}
              className={`${item} w-full text-left`}
            >
              {t.account.signOut}
            </button>
          </div>
        </div>
      )}
    </Popover>
  );
}
