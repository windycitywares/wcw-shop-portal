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
      { href: "/admin/settings", label: "Store settings", icon: "sliders", permission: "settings:manage", hidden: true },
      { href: "/admin/team", label: "Team", icon: "users", permission: "users:manage" },
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
