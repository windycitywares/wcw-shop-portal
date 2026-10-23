import type { IconName } from "./ui/Icon";

export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  /** Permission needed to see the link (the API enforces it as well). null = any staff. */
  permission: string | null;
  /** Only shown in the settings page's left panel, not in the main sidebar. */
  hidden?: boolean;
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
      { href: "/admin/analytics/sales", label: "Sales report", icon: "chart", permission: "reports:view" },
      { href: "/admin/carts", label: "Abandoned carts", icon: "cart", permission: "customers:view" },
      { href: "/admin/analytics", label: "All reports", icon: "chart", permission: "reports:view" },
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
];

function matches(pathname: string, href: string): boolean {
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** The one menu link for this page: the longest href that matches, so /admin/analytics/sales marks
 *  "Sales report" and not "All reports" as well. */
export function activeHref(pathname: string): string | undefined {
  return NAV.flatMap((g) => g.items)
    .map((i) => i.href)
    .filter((h) => matches(pathname, h))
    .sort((a, b) => b.length - a.length)[0];
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
export const SETTINGS_TABS: { id: string; label: string }[] = [
  { id: "shipping", label: "Shipping" },
  { id: "tax", label: "Sales tax" },
  { id: "payments", label: "Payments" },
  { id: "welcome", label: "Welcome offer" },
  { id: "cart_recovery", label: "Cart reminders" },
  { id: "reviews", label: "Reviews" },
  { id: "analytics", label: "Analytics" },
  { id: "digest", label: "Weekly email" },
  { id: "general", label: "General" },
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
];

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
      const t = SETTINGS_TABS.find((x) => x.id === tab) ?? SETTINGS_TABS[0];
      crumbs.push({ label: "Settings", href: "/admin/settings" }, { label: t.label });
      return crumbs;
    }
    crumbs.push({ label: "Settings", href: "/admin/settings" });
  } else {
    const group = NAV.find((g) => g.label && g.items.some((i) => i.href === href));
    if (group?.label) crumbs.push({ label: group.label });
  }
  if (item) {
    const deeper = pathname.length > item.href.length;
    crumbs.push(deeper ? { label: item.label, href: item.href } : { label: item.label });
    if (deeper) crumbs.push({ label: "Details" });
  }
  return crumbs;
}
