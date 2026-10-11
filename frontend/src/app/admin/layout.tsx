"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { isStaff, useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Container } from "@/components/ui/misc";

const NAV = [
  { href: "/admin", label: "Dashboard", permission: null },
  { href: "/admin/products", label: "Products", permission: "catalog:view_unpublished" },
  { href: "/admin/import", label: "Import / Export", permission: "catalog:import" },
  { href: "/admin/categories", label: "Categories", permission: "category:manage" },
  { href: "/admin/users", label: "Users", permission: "users:manage" },
];

/** Client-side gate for the admin UI. The API enforces every permission independently. */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, can } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (!isStaff(user)) router.replace("/account");
  }, [loading, user, router, pathname]);

  if (!user || !isStaff(user)) {
    return <Container className="py-16 text-muted">Checking access…</Container>;
  }

  return (
    <Container className="grid gap-8 py-10 lg:grid-cols-[13rem_1fr]">
      <nav aria-label="Admin">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
          Admin · <span className="capitalize">{user.role}</span>
        </p>
        <ul className="flex gap-1 overflow-x-auto lg:flex-col">
          {NAV.filter((n) => !n.permission || can(n.permission)).map((n) => {
            const active = n.href === "/admin" ? pathname === "/admin" : pathname.startsWith(n.href);
            return (
              <li key={n.href}>
                <Link
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "block whitespace-nowrap rounded-lg px-3 py-2 text-sm",
                    active ? "bg-ink text-white" : "hover:bg-sand",
                  )}
                >
                  {n.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="min-w-0">{children}</div>
    </Container>
  );
}
