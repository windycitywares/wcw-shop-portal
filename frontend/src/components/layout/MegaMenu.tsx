"use client";

import { ChevronDown } from "@untitledui/icons";
import * as NavigationMenu from "@radix-ui/react-navigation-menu";
import Link from "next/link";
import { useI18n } from "@/i18n/client";
import type { CategoryNode } from "@/lib/types";
import { Container } from "@/components/ui/misc";

const linkClass =
  "inline-flex h-10 items-center rounded-full px-3.5 text-[0.9375rem] text-ink hover:bg-sand data-[state=open]:bg-sand";

/**
 * Desktop navigation from the category tree (keyboard + screen-reader accessible via Radix).
 * The panel spans the whole header: the Root is left unpositioned so the sticky <header> anchors it.
 */
export function MegaMenu({ tree }: { tree: CategoryNode[] }) {
  const { t, href, fmt } = useI18n();
  return (
    <NavigationMenu.Root aria-label={t.nav.categories} className="static">
      <NavigationMenu.List className="flex items-center gap-1">
        <NavigationMenu.Item>
          <NavigationMenu.Link asChild>
            <Link href={href("/shop")} className={linkClass}>
              {t.nav.shopAll}
            </Link>
          </NavigationMenu.Link>
        </NavigationMenu.Item>
        <NavigationMenu.Item>
          <NavigationMenu.Link asChild>
            <Link href={href("/deals")} className={linkClass}>
              {t.nav.deals}
            </Link>
          </NavigationMenu.Link>
        </NavigationMenu.Item>
        {tree.map((node) =>
          node.children.length === 0 ? (
            <NavigationMenu.Item key={node.id}>
              <NavigationMenu.Link asChild>
                <Link href={href(`/category/${node.slug}`)} className={linkClass}>
                  {node.name}
                </Link>
              </NavigationMenu.Link>
            </NavigationMenu.Item>
          ) : (
            <NavigationMenu.Item key={node.id}>
              <NavigationMenu.Trigger className={`${linkClass} group gap-1.5`}>
                {node.name}
                <ChevronDown aria-hidden="true" className="size-3.5 transition-transform group-data-[state=open]:rotate-180" />
              </NavigationMenu.Trigger>
              <NavigationMenu.Content className="w-full">
                <Container className="grid grid-cols-[18rem_1fr] gap-12 py-10">
                  <div>
                    <p className="font-serif text-3xl font-light">{node.name}</p>
                    {node.description && <p className="mt-3 text-sm text-muted">{node.description}</p>}
                    <NavigationMenu.Link asChild>
                      <Link
                        href={href(`/category/${node.slug}`)}
                        className="mt-5 inline-block text-sm font-medium text-accent underline underline-offset-4 hover:text-accent-strong"
                      >
                        {fmt(t.nav.shopAllIn, { name: node.name })}
                      </Link>
                    </NavigationMenu.Link>
                  </div>
                  <ul className="grid grid-cols-3 content-start gap-x-8 gap-y-1">
                    {node.children.map((child) => (
                      <li key={child.id}>
                        <NavigationMenu.Link asChild>
                          <Link
                            href={href(`/category/${child.slug}`)}
                            className="block border-b border-line py-2.5 text-[0.9375rem] hover:text-accent"
                          >
                            {child.name}
                          </Link>
                        </NavigationMenu.Link>
                      </li>
                    ))}
                  </ul>
                </Container>
              </NavigationMenu.Content>
            </NavigationMenu.Item>
          ),
        )}
      </NavigationMenu.List>
      <div className="absolute left-0 top-full w-full">
        <NavigationMenu.Viewport className="relative h-[var(--radix-navigation-menu-viewport-height)] w-full overflow-hidden border-b border-line bg-surface shadow-[0_24px_48px_-24px_rgb(23_35_43/0.25)] transition-[height] duration-200" />
      </div>
    </NavigationMenu.Root>
  );
}
