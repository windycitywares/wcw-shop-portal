import type { IconName } from "./ui/Icon";

export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  /** Permission needed to see the link (the API enforces it as well). null = any staff. */
  permission: string | null;
  /** Only shown in the settings page's left panel, not in the main sidebar. */
  hidden?: boolean;
  /** Other path prefixes that also mean "this item" (a menu entry that covers several pages). */
  also?: string[];
}
export interface NavGroup {
  label: string | null;
  items: NavItem[];
}

/** Sidebar structure. Add a page here and it appears for roles that hold its permission. */
export const NAV: NavGroup[] = [
  {
    label: null,
    items: [
      { href: "/admin", label: "Dashboard", icon: "dashboard", permission: null },
    ],
  },
  {
    // Everything about money coming in: every order, the totals over time, and carts left before paying.
    label: "Sales",
    items: [
      { href: "/admin/orders", label: "All orders", icon: "orders", permission: "orders:manage" },
      { href: "/admin/carts", label: "Abandoned carts", icon: "cart", permission: "customers:view" },
    ],
  },
  {
    // Reports, grouped by the question each answers; the tabs inside the page list that group's reports.
    label: "Analytics",
    items: [
      { href: "/admin/analytics", label: "Overview", icon: "bulb", permission: "reports:view" },
      { href: "/admin/analytics/traffic", label: "Visitors", icon: "globe", permission: "reports:view", also: ["/admin/analytics/behavior", "/admin/analytics/performance"] },
      { href: "/admin/analytics/sales", label: "Sales report", icon: "chart", permission: "reports:view", also: ["/admin/analytics/funnel", "/admin/analytics/promotions"] },
      { href: "/admin/analytics/products", label: "Product reports", icon: "products", permission: "reports:view", also: ["/admin/analytics/inventory", "/admin/analytics/catalog"] },
      { href: "/admin/analytics/customers", label: "Customer reports", icon: "customers", permission: "customers:view" },
    ],
  },
  {
    // The people: who buys, who signed up, and what they asked us.
    label: "Customers",
    items: [
      { href: "/admin/customers", label: "Customers", icon: "customers", permission: "customers:view" },
      { href: "/admin/messages", label: "Messages", icon: "inbox", permission: "messages:manage" },
      { href: "/admin/stock-requests", label: "Stock requests", icon: "bell", permission: "customers:view" },
    ],
  },
  {
    // Bringing people back: discounts, newsletters and the list they go to.
    label: "Marketing",
    items: [
      { href: "/admin/promotions", label: "Promotions", icon: "tag", permission: "promotions:manage" },
      { href: "/admin/campaigns", label: "Email campaigns", icon: "mail", permission: "promotions:manage" },
      { href: "/admin/subscribers", label: "Subscribers", icon: "users", permission: "customers:view" },
    ],
  },
  {
    label: "Catalog",
    items: [
      { href: "/admin/products", label: "Products", icon: "products", permission: "catalog:view_unpublished" },
      { href: "/admin/categories", label: "Categories", icon: "categories", permission: "category:manage" },
      { href: "/admin/import", label: "Import and export", icon: "import", permission: "catalog:import" },
      { href: "/admin/reviews", label: "Reviews", icon: "star", permission: "reviews:moderate" },
    ],
  },
  {
    label: "Settings",
    items: [
      { href: "/admin/settings", label: "Settings", icon: "sliders", permission: "settings:manage" },
      { href: "/admin/team", label: "Team", icon: "users", permission: "users:manage" },
      { href: "/admin/email", label: "Email sending", icon: "mail", permission: "settings:manage", hidden: true },
      { href: "/admin/email-templates", label: "Email templates", icon: "mail", permission: "settings:manage", hidden: true },
      { href: "/admin/audit", label: "Audit log", icon: "shield", permission: "audit:view", hidden: true },
      { href: "/admin/environment", label: "Test mode", icon: "flask", permission: "environment:manage", hidden: true },
      { href: "/admin/backups", label: "Backups", icon: "archive", permission: "backups:manage", hidden: true },
      { href: "/admin/deployments", label: "Deployments", icon: "download", permission: "settings:manage", hidden: true },
    ],
  },
  {
    label: "Help",
    items: [{ href: "/admin/wiki", label: "Admin wiki", icon: "bulb", permission: null }],
  },
];

function matches(pathname: string, href: string): boolean {
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** The one menu link for this page: the longest href that matches, so /admin/analytics/sales marks
 *  "Sales report" and not "All reports" as well. */
export function activeHref(pathname: string): string | undefined {
  let best: { href: string; len: number } | undefined;
  for (const item of NAV.flatMap((g) => g.items)) {
    for (const h of [item.href, ...(item.also ?? [])]) {
      if (matches(pathname, h) && (!best || h.length > best.len)) best = { href: item.href, len: h.length };
    }
  }
  return best?.href;
}

export function isActive(pathname: string, href: string): boolean {
  return activeHref(pathname) === href;
}

/** Title for the browser tab / mobile header from the current path. */
export function titleFor(pathname: string): string {
  const href = activeHref(pathname);
  return NAV.flatMap((g) => g.items).find((i) => i.href === href)?.label ?? "Admin";
}

/** The store settings sections (each is /admin/settings?tab=<id>). */
export const SETTINGS_TABS: { id: string; label: string; about: string }[] = [
  { id: "shipping", label: "Shipping", about: "What shipping costs, free shipping, and how many days it takes." },
  { id: "tax", label: "Sales tax", about: "Whether you collect sales tax, the rate and the states." },
  { id: "payments", label: "Payments", about: "Card payments and what customers see when an order is waiting for money." },
  { id: "welcome", label: "Welcome offer", about: "The discount code new newsletter subscribers receive." },
  { id: "cart_recovery", label: "Cart reminders", about: "Friendly reminders to people who left items in their cart." },
  { id: "reviews", label: "Reviews", about: "How reviews are collected and published." },
  { id: "analytics", label: "Analytics", about: "Visit statistics, for visitors who agree to them." },
  { id: "digest", label: "Weekly email", about: "The Monday summary email of last week’s numbers." },
  { id: "general", label: "General", about: "Announcement bar, order alerts and checkout rules." },
];

/** Pages that belong to Settings: while on one, the sidebar shows this menu instead of the main one. */
export const SETTINGS_HREFS = [
  "/admin/email",
  "/admin/email-templates",
  "/admin/team",
  "/admin/audit",
  "/admin/environment",
  "/admin/backups",
  "/admin/deployments",
  "/admin/wiki",
];

/** One plain sentence per admin tool, for the Settings overview. */
export const TOOL_ABOUT: Record<string, string> = {
  "/admin/email": "Which address your emails come from and the mail server that sends them. Send yourself a test.",
  "/admin/email-templates": "Change the wording of the welcome, password-reset and order emails.",
  "/admin/team": "Who can sign in to this admin, and what each person may do.",
  "/admin/audit": "A record of who changed what, and when.",
  "/admin/environment": "Practise on a copy of the shop's data without touching the real shop.",
  "/admin/backups": "Save and restore copies of the shop's data.",
  "/admin/deployments": "Publish the latest changes to the live shop.",
  "/admin/wiki": "Plain-language help for running the shop and every setting. Staff only.",
};

export function inSettings(pathname: string): boolean {
  return matches(pathname, "/admin/settings") || SETTINGS_HREFS.some((h) => matches(pathname, h));
}

export function settingsPages(): NavItem[] {
  return SETTINGS_HREFS.map((h) => NAV.flatMap((g) => g.items).find((i) => i.href === h)).filter((i): i is NavItem => !!i);
}

export interface Crumb {
  label: string;
  href?: string;
}

/** Dashboard › section › page, for the strip above every admin page. */
export function crumbsFor(pathname: string, tab: string | null): Crumb[] {
  if (pathname === "/admin") return [];
  const crumbs: Crumb[] = [{ label: "Dashboard", href: "/admin" }];
  const items = NAV.flatMap((g) => g.items);
  const href = activeHref(pathname);
  const item = items.find((i) => i.href === href);
  if (inSettings(pathname)) {
    if (matches(pathname, "/admin/settings")) {
      const t = SETTINGS_TABS.find((x) => x.id === tab);
      crumbs.push(t ? { label: "Settings", href: "/admin/settings" } : { label: "Settings" });
      if (t) crumbs.push({ label: t.label });
      return crumbs;
    }
    crumbs.push({ label: "Settings", href: "/admin/settings" });
  } else {
    const group = NAV.find((g) => g.label && g.items.some((i) => i.href === href));
    if (group?.label) crumbs.push({ label: group.label });
  }
  if (item) {
    const deeper = pathname.startsWith(`${item.href}/`);
    crumbs.push(deeper ? { label: item.label, href: item.href } : { label: item.label });
    if (deeper) crumbs.push({ label: "Details" });
  }
  return crumbs;
}
