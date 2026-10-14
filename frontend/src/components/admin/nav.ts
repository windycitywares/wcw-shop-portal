import type { IconName } from "./ui/Icon";

export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  /** Permission needed to see the link (the API enforces it as well). null = any staff. */
  permission: string | null;
}
export interface NavGroup {
  label: string | null;
  items: NavItem[];
}

/** Sidebar structure. Add a page here and it appears for roles that hold its permission. */
export const NAV: NavGroup[] = [
  { label: null, items: [{ href: "/admin", label: "Dashboard", icon: "dashboard", permission: null }] },
  {
    label: "Sales",
    items: [
      { href: "/admin/orders", label: "Orders", icon: "orders", permission: "orders:manage" },
      { href: "/admin/promotions", label: "Promotions", icon: "tag", permission: "promotions:manage" },
      { href: "/admin/messages", label: "Messages", icon: "mail", permission: "orders:manage" },
    ],
  },
  {
    label: "Catalog",
    items: [
      { href: "/admin/products", label: "Products", icon: "products", permission: "catalog:view_unpublished" },
      { href: "/admin/categories", label: "Categories", icon: "categories", permission: "category:manage" },
      { href: "/admin/import", label: "Import and export", icon: "import", permission: "catalog:import" },
    ],
  },
  {
    label: "Store",
    items: [
      { href: "/admin/settings", label: "Settings", icon: "sliders", permission: "settings:manage" },
      { href: "/admin/users", label: "Team and customers", icon: "users", permission: "users:manage" },
    ],
  },
];

export function isActive(pathname: string, href: string): boolean {
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Title for the browser tab / mobile header from the current path. */
export function titleFor(pathname: string): string {
  const all = NAV.flatMap((g) => g.items).sort((a, b) => b.href.length - a.href.length);
  return all.find((i) => isActive(pathname, i.href))?.label ?? "Admin";
}
