/** Which notification setting (Admin → Notification settings) a live event belongs to. Mirrors app/domain/live_prefs.py. */
export type LiveCategory =
  | "orders_new"
  | "orders_payments"
  | "orders_status"
  | "messages"
  | "customers"
  | "newsletter"
  | "reviews"
  | "stock"
  | "products"
  | "backups";

export function categoryOf(kind: string): LiveCategory | null {
  if (kind === "order.new") return "orders_new";
  if (kind === "order.paid" || kind === "order.refund") return "orders_payments";
  if (kind === "order.status") return "orders_status";
  if (kind.startsWith("message.")) return "messages";
  if (kind.startsWith("customer.")) return "customers";
  if (kind.startsWith("subscriber.")) return "newsletter";
  if (kind.startsWith("review.")) return "reviews";
  if (kind.startsWith("stock_request.")) return "stock";
  if (kind.startsWith("product.")) return "products";
  if (kind.startsWith("backup.")) return "backups";
  return null;
}

export type Channels = { popup: boolean; sound: boolean; desktop: boolean };
export type SoundName = "chime" | "bell" | "pop";
export interface NotificationPrefs {
  categories: Record<LiveCategory, Channels>;
  sound: SoundName;
  volume: number; // 0–100
  refresh_bars: boolean;
  new_version: boolean;
}

/** Until the person's own settings arrive (or if they can't be loaded): the same defaults as the API. */
export const DEFAULT_PREFS: NotificationPrefs = {
  categories: {
    orders_new: { popup: true, sound: true, desktop: false },
    orders_payments: { popup: false, sound: false, desktop: false },
    orders_status: { popup: false, sound: false, desktop: false },
    messages: { popup: true, sound: false, desktop: false },
    customers: { popup: false, sound: false, desktop: false },
    newsletter: { popup: false, sound: false, desktop: false },
    reviews: { popup: false, sound: false, desktop: false },
    stock: { popup: false, sound: false, desktop: false },
    products: { popup: false, sound: false, desktop: false },
    backups: { popup: true, sound: false, desktop: false },
  },
  sound: "chime",
  volume: 70,
  refresh_bars: true,
  new_version: true,
};

/** What to do with a batch of events: who pops up, whether to play a sound, which desktop alerts to show. */
export function plan(events: { kind: string }[], prefs: NotificationPrefs) {
  const on = (kind: string, ch: keyof Channels) => {
    const c = categoryOf(kind);
    return !!c && !!prefs.categories[c]?.[ch];
  };
  return {
    popups: events.filter((e) => on(e.kind, "popup")),
    sound: prefs.volume > 0 && events.some((e) => on(e.kind, "sound")),
    desktop: events.filter((e) => on(e.kind, "desktop")),
  };
}
