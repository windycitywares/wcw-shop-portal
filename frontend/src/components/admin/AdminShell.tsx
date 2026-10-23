"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { isStaff, useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/ui/Logo";
import { ThemeSwitcher } from "@/components/layout/ThemeSwitcher";
import { TestModeBanner } from "@/components/TestModeBanner";
import { NotificationBell } from "./notifications/NotificationBell";
import { NAV, SETTINGS_TABS, crumbsFor, inSettings, isActive, settingsPages, titleFor } from "./nav";
import { Icon } from "./ui/Icon";
import { Popover } from "@/components/ui/Popover";
import { Badge } from "@/components/ui/Badge";
import { Avatar } from "@/components/ui/Avatar";
import { ToastProvider } from "./ui/Toast";

const linkClass = (active: boolean, collapsed: boolean) =>
  cn(
    "font-admin group relative flex items-center gap-3 rounded-[var(--radius-control)] py-2 text-[0.95rem] transition-[color,background-color,transform] duration-150 focus-visible:outline-offset-0",
    collapsed ? "justify-center px-2" : "px-3",
    active ? "bg-sand font-bold text-ink" : "text-ink hover:bg-sand/60 hover:text-accent motion-safe:hover:translate-x-0.5",
  );

/** The menu while in Settings: a way back to the dashboard, the store settings sections, and the admin tools. */
function SettingsNav({ onNavigate, collapsed }: { onNavigate?: () => void; collapsed: boolean }) {
  const { can } = useAuth();
  const pathname = usePathname();
  const tab = useSearchParams().get("tab");
  const onSettingsPage = pathname === "/admin/settings";
  const current = onSettingsPage ? (SETTINGS_TABS.some((t) => t.id === tab) ? tab : "overview") : null;
  const tools = settingsPages().filter((i) => !i.permission || can(i.permission));
  const showStore = can("settings:manage");
  return (
    <nav aria-label="Settings" className={cn("flex-1 overflow-y-auto pb-6 pt-2", collapsed ? "px-2" : "px-4")}>
      <Link
        href="/admin"
        onClick={onNavigate}
        title={collapsed ? "Back to dashboard" : undefined}
        className={cn(
          "font-admin mb-4 flex items-center gap-2 rounded-[var(--radius-control)] border border-line py-2 text-sm font-semibold text-ink hover:border-accent hover:text-accent",
          collapsed ? "justify-center px-2" : "px-3",
        )}>
        <Icon name="chevronLeft" className="size-4 shrink-0" />
        {collapsed ? <span className="sr-only">Back to dashboard</span> : "Back to dashboard"}
      </Link>
      {showStore && (
        <div>
          {collapsed ? <hr className="mx-2 mb-2 border-line" /> : <p className="font-admin px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-muted">Store settings</p>}
          <ul className="space-y-0.5">
            <li>
              <Link href="/admin/settings" onClick={onNavigate} aria-current={current === "overview" ? "page" : undefined} title={collapsed ? "All settings" : undefined} className={linkClass(current === "overview", collapsed)}>
                {current === "overview" && <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-accent" />}
                <Icon name="dashboard" className={cn("size-[1.15rem] shrink-0", current === "overview" ? "text-accent" : "text-muted group-hover:text-accent")} />
                {!collapsed && <span>All settings</span>}
              </Link>
            </li>
            {SETTINGS_TABS.map((t) => {
              const active = current === t.id;
              return (
                <li key={t.id}>
                  <Link href={`/admin/settings?tab=${t.id}`} onClick={onNavigate} aria-current={active ? "page" : undefined} title={collapsed ? t.label : undefined} className={linkClass(active, collapsed)}>
                    {active && <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-accent" />}
                    <Icon name="sliders" className={cn("size-[1.15rem] shrink-0", active ? "text-accent" : "text-muted group-hover:text-accent")} />
                    {!collapsed && <span>{t.label}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {tools.length > 0 && (
        <div className="mt-4">
          {collapsed ? <hr className="mx-2 mb-2 border-line" /> : <p className="font-admin px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-muted">Admin</p>}
          <ul className="space-y-0.5">
            {tools.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <li key={item.href}>
                  <Link href={item.href} onClick={onNavigate} aria-current={active ? "page" : undefined} title={collapsed ? item.label : undefined} className={linkClass(active, collapsed)}>
                    {active && <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-accent" />}
                    <Icon name={item.icon} className={cn("size-[1.15rem] shrink-0", active ? "text-accent" : "text-muted group-hover:text-accent")} />
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </nav>
  );
}

/** Dashboard › Settings › Shipping: where you are, with a link back up. */
function Crumbs() {
  const pathname = usePathname();
  const crumbs = crumbsFor(pathname, useSearchParams().get("tab"));
  if (crumbs.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className="mb-4">
      <ol className="font-admin flex flex-wrap items-center gap-1.5 text-sm text-muted">
        {crumbs.map((c, i) => (
          <li key={`${c.label}-${i}`} className="flex items-center gap-1.5">
            {i > 0 && <Icon name="chevronRight" className="size-3.5" />}
            {c.href && i < crumbs.length - 1 ? (
              <Link href={c.href} className="hover:text-accent hover:underline">
                {c.label}
              </Link>
            ) : (
              <span aria-current={i === crumbs.length - 1 ? "page" : undefined} className={i === crumbs.length - 1 ? "font-medium text-ink" : undefined}>
                {c.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

function SidebarNav({ onNavigate, collapsed }: { onNavigate?: () => void; collapsed: boolean }) {
  const { can } = useAuth();
  const pathname = usePathname();
  if (inSettings(pathname)) {
    return (
      <Suspense fallback={null}>
        <SettingsNav onNavigate={onNavigate} collapsed={collapsed} />
      </Suspense>
    );
  }
  return (
    <nav aria-label="Admin" className={cn("flex-1 overflow-y-auto pb-6 pt-2", collapsed ? "px-2" : "px-4")}>
      {NAV.map((group, gi) => {
        const items = group.items.filter((i) => !i.hidden && (!i.permission || can(i.permission)));
        if (items.length === 0) return null;
        return (
          <div key={group.label ?? gi} className={gi > 0 ? "mt-4" : ""}>
            {group.label &&
              (collapsed ? (
                <hr className="mx-2 mb-2 border-line" />
              ) : (
                <p className="font-admin px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-muted">{group.label}</p>
              ))}
            <ul className="space-y-0.5">
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        "font-admin group relative flex items-center gap-3 rounded-[var(--radius-control)] py-2 text-[0.95rem] transition-[color,background-color,transform] duration-150 focus-visible:outline-offset-0",
                        collapsed ? "justify-center px-2" : "px-3",
                        active ? "bg-sand font-bold text-ink" : "text-ink hover:bg-sand/60 hover:text-accent motion-safe:hover:translate-x-0.5",
                      )}>
                      {active && (
                        <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-accent" />
                      )}
                      <Icon name={item.icon} className={cn("size-[1.15rem] shrink-0", active ? "text-accent" : "text-muted group-hover:text-accent")} />
                      {!collapsed && <span>{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link href="/admin" className="flex min-w-0 items-center gap-3 rounded-[var(--radius-control)] px-1 py-1" aria-label="WindyCityWares admin home">
      <span aria-hidden="true" className="font-admin grid size-9 shrink-0 place-items-center rounded-lg bg-accent text-base font-bold text-on-accent shadow-[var(--shadow-card)]">
        W
      </span>
      {!collapsed && <span className="font-admin truncate text-lg font-semibold text-ink">WCW Admin</span>}
    </Link>
  );
}

/** Client-side gate and frame for the admin UI. The API enforces every permission independently. */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (!isStaff(user)) router.replace("/account");
  }, [loading, user, router, pathname]);

  useEffect(() => setDrawer(false), [pathname]);
  useEffect(() => {
    document.title = `${titleFor(pathname)} | Admin | WindyCityWares`;
  }, [pathname]);

  if (!user || !isStaff(user)) {
    return <div className="grid min-h-dvh place-items-center text-sm text-muted">Checking access…</div>;
  }

  return (
    <ToastProvider>
      <a href="#admin-main" className="skip-link">
        Skip to content
      </a>
      <div className={cn("min-h-dvh lg:grid", collapsed ? "lg:grid-cols-[4.5rem_minmax(0,1fr)]" : "lg:grid-cols-[16rem_minmax(0,1fr)]")}>
        {/* Sidebar: a white menu with a soft shadow; the current page has a tint, an accent bar and an accent icon */}
        <aside className="sticky top-0 z-20 hidden h-dvh flex-col bg-surface shadow-[var(--shadow-card)] lg:flex">
          <div className={cn("flex h-16 shrink-0 items-center gap-2", collapsed ? "flex-col justify-center px-2" : "justify-between pl-4 pr-3")}>
            {!collapsed && <Brand collapsed={false} />}
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              aria-expanded={!collapsed}
              className="grid size-9 shrink-0 place-items-center rounded-[var(--radius-control)] text-muted hover:bg-sand hover:text-accent"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
              <Icon name="menu" className="size-5" />
              <span className="sr-only">{collapsed ? "Expand sidebar" : "Collapse sidebar"}</span>
            </button>
          </div>
          <SidebarNav onNavigate={() => setDrawer(false)} collapsed={collapsed} />
        </aside>

        <div className="flex min-w-0 flex-col">
          <TestModeBanner label="Test mode" text="Test mode: you're working on a copy of the shop's data. Nothing here changes the live shop.">
            {" "}
            <Link href="/admin/environment" className="underline underline-offset-4">
              Test mode settings
            </Link>
          </TestModeBanner>
          <header className="sticky top-0 z-30 flex h-16 items-center gap-2 bg-surface px-4 shadow-[var(--shadow-card)] sm:px-6 lg:px-8">
            <Dialog.Root open={drawer} onOpenChange={setDrawer}>
              <Dialog.Trigger className="-ml-1 grid size-10 place-items-center rounded-[var(--radius-control)] hover:bg-sand lg:hidden">
                <Icon name="menu" className="size-5" />
                <span className="sr-only">Open admin menu</span>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-night/50 lg:hidden" />
                <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-surface shadow-[var(--shadow-raised)] lg:hidden">
                  <Dialog.Title className="sr-only">Admin menu</Dialog.Title>
                  <Dialog.Description className="sr-only">Go to a section of the admin.</Dialog.Description>
                  <div className="flex h-16 items-center justify-between pl-4 pr-3">
                    <Brand collapsed={false} />
                    <Dialog.Close className="grid size-9 place-items-center rounded-full text-muted hover:bg-sand hover:text-ink">
                      <Icon name="close" className="size-5" />
                      <span className="sr-only">Close menu</span>
                    </Dialog.Close>
                  </div>
                  <SidebarNav onNavigate={() => setDrawer(false)} collapsed={false} />
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>

            <form
              role="search"
              className="ml-2 hidden max-w-[26rem] flex-1 sm:flex"
              onSubmit={(e) => {
                e.preventDefault();
                const q = String(new FormData(e.currentTarget).get("q") || "").trim();
                if (!q) return;
                // An email finds the customer; anything else (an order number, a name) searches orders.
                window.location.assign(`${q.includes("@") ? "/admin/customers" : "/admin/orders"}?q=${encodeURIComponent(q)}`);
              }}>
              <label htmlFor="admin-search" className="sr-only">
                Search the admin
              </label>
              <div className="relative w-full">
                <Icon name="search" className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
                <input
                  id="admin-search"
                  name="q"
                  type="search"
                  placeholder="Order number, customer email…"
                  className="w-full rounded-full border border-line bg-canvas py-2 pl-10 pr-4 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none"
                />
              </div>
            </form>

            <div className="ml-auto flex items-center gap-2">
              <NotificationBell />
              <ThemeSwitcher />
              <Popover
                label="Account menu"
                trigger={
                  <div className="flex items-center gap-2">
                    <Avatar name={user.full_name ?? user.email} size="sm" status="online" />
                    <span className="hidden sm:inline truncate max-w-[14rem] text-sm font-medium text-ink">{user.full_name || user.email}</span>
                    <Icon name="chevronDown" className="size-4 text-muted" />
                  </div>
                }
                triggerClassName="border-transparent bg-transparent hover:bg-sand"
                panelClassName="w-64">
                {(close) => (
                  <div>
                    <div className="px-3 py-2">
                      <p className="truncate text-sm font-medium text-ink">{user.full_name || "Signed in"}</p>
                      <p className="truncate text-xs text-muted">{user.email}</p>
                      <p className="mt-1 text-xs capitalize text-muted">{user.role} access</p>
                    </div>
                    <div className="border-t border-line pt-1">
                      <Link href="/admin/settings" onClick={close} className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand">
                        <Icon name="sliders" className="size-4 text-muted" />
                        Settings
                      </Link>
                      <Link href="/account" onClick={close} className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand">
                        <Icon name="customers" className="size-4 text-muted" />
                        Your account
                      </Link>
                      <button
                        type="button"
                        onClick={() => {
                          close();
                          logout();
                          router.push("/login");
                        }}
                        className="flex w-full items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-left text-sm hover:bg-sand">
                        <Icon name="logout" className="size-4 text-muted" />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </Popover>
            </div>
          </header>

          <main id="admin-main" tabIndex={-1} className="mx-auto w-full max-w-[92rem] flex-1 px-4 py-6 focus:outline-none sm:px-6 lg:px-8 lg:py-8">
            <Suspense fallback={null}>
              <Crumbs />
            </Suspense>
            {children}
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
