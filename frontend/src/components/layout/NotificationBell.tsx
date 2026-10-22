"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { fmt, intlLocale } from "@/i18n/config";
import { useI18n } from "@/i18n/client";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { formatPrice } from "@/lib/utils";
import { Popover } from "@/components/ui/Popover";

type Kind = "placed" | "paid" | "shipped" | "delivered" | "cancelled" | "refunded";

interface Item {
  id: string;
  kind: Kind;
  order_id: number;
  number: string;
  token: string | null;
  at: string;
  amount: number | null;
  unread: boolean;
}

interface Feed {
  items: Item[];
  unread: number;
}

const item = "block rounded-[var(--radius-control)] px-3 py-2 hover:bg-sand";

/** A date the shopper can place: "Oct 19, 2026". */
function when(iso: string, locale: keyof typeof intlLocale) {
  return new Intl.DateTimeFormat(intlLocale[locale], { dateStyle: "medium" }).format(new Date(iso));
}

/**
 * The bell beside the account menu: order activity (placed, shipped, delivered, cancelled, refunded)
 * for the signed-in shopper, unread until they open it. Nothing is shown to visitors who aren't signed in.
 */
export function NotificationBell() {
  const { user } = useAuth();
  const { t, href, locale } = useI18n();
  const [feed, setFeed] = useState<Feed>({ items: [], unread: 0 });

  const load = useCallback(async () => {
    try {
      setFeed(await apiFetch<Feed>("/account/notifications"));
    } catch {
      /* a quiet bell beats an error box in the header */
    }
  }, []);

  useEffect(() => {
    if (user) void load();
    else setFeed({ items: [], unread: 0 });
  }, [user, load]);

  if (!user) return null;

  // Opening the list is reading it: clear the badge, tell the API, then show the fresh list.
  const opened = (open: boolean) => {
    if (!open) return;
    if (feed.unread) {
      setFeed((f) => ({ ...f, unread: 0, items: f.items.map((i) => ({ ...i, unread: false })) }));
      void apiFetch("/account/notifications/seen", { method: "POST" }).catch(() => {}).then(load);
      return;
    }
    void load();
  };

  const words = (i: Item) => {
    const vars = { number: i.number, amount: i.amount != null ? formatPrice(i.amount, "USD", locale) : "" };
    switch (i.kind) {
      case "placed":
        return fmt(t.notifications.placed, vars);
      case "paid":
        return fmt(t.notifications.paid, vars);
      case "shipped":
        return fmt(t.notifications.shipped, vars);
      case "delivered":
        return fmt(t.notifications.delivered, vars);
      case "cancelled":
        return fmt(t.notifications.cancelled, vars);
      default:
        return fmt(t.notifications.refunded, vars);
    }
  };

  return (
    <Popover
      label={t.notifications.title}
      title={t.notifications.title}
      className="shrink-0"
      triggerClassName="relative h-10 w-10 justify-center border-transparent bg-transparent px-0 hover:border-transparent hover:bg-sand"
      panelClassName="w-80 p-0"
      onOpenChange={opened}
      trigger={
        <>
          <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M6 9a6 6 0 1 1 12 0c0 4 1.5 5.2 1.5 5.2h-15S6 13 6 9Z" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M10 18.5a2 2 0 0 0 4 0" strokeLinecap="round" />
          </svg>
          {feed.unread > 0 && (
            <span className="absolute right-1.5 top-1.5 grid min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] font-semibold leading-4 text-white">
              {feed.unread > 9 ? "9+" : feed.unread}
            </span>
          )}
        </>
      }
    >
      {(close) => (
        <div>
          <p className="px-3 py-2 text-sm font-medium">{t.notifications.title}</p>
          {feed.items.length === 0 ? (
            <p className="px-3 pb-3 text-sm text-muted">{t.notifications.empty}</p>
          ) : (
            <ul className="max-h-80 overflow-y-auto border-t border-line pt-1">
              {feed.items.map((i) => (
                <li key={i.id}>
                  <Link
                    href={i.token ? href(`/order/${i.token}`) : `${href("/account")}#my-orders`}
                    onClick={close}
                    className={item}
                  >
                    <span className={i.unread ? "block text-sm font-medium" : "block text-sm"}>{words(i)}</span>
                    <span className="block text-xs text-muted">{when(i.at, locale)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-line p-1.5">
            <Link href={`${href("/account")}#my-orders`} onClick={close} className={item}>
              {t.notifications.viewAll}
            </Link>
          </div>
        </div>
      )}
    </Popover>
  );
}
