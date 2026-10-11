"use client";

import * as NavigationMenu from "@radix-ui/react-navigation-menu";
import Link from "next/link";
import type { CategoryNode } from "@/lib/types";
import { Container } from "@/components/ui/misc";

const linkClass =
  "inline-flex h-11 items-center rounded-md px-3 text-sm font-medium text-ink hover:text-accent data-[state=open]:text-accent";

/** Desktop navigation generated from the category tree (keyboard + screen-reader accessible via Radix). */
export function MegaMenu({ tree }: { tree: CategoryNode[] }) {
  return (
    <NavigationMenu.Root aria-label="Shop categories" className="relative hidden md:block">
      <Container>
        <NavigationMenu.List className="flex items-center gap-1">
          <NavigationMenu.Item>
            <NavigationMenu.Link asChild>
              <Link href="/shop" className={linkClass}>
                Shop all
              </Link>
            </NavigationMenu.Link>
          </NavigationMenu.Item>
          {tree.map((node) =>
            node.children.length === 0 ? (
              <NavigationMenu.Item key={node.id}>
                <NavigationMenu.Link asChild>
                  <Link href={`/category/${node.slug}`} className={linkClass}>
                    {node.name}
                  </Link>
                </NavigationMenu.Link>
              </NavigationMenu.Item>
            ) : (
              <NavigationMenu.Item key={node.id}>
                <NavigationMenu.Trigger className={`${linkClass} group gap-1`}>
                  {node.name}
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 12 12"
                    className="size-3 transition-transform group-data-[state=open]:rotate-180"
                  >
                    <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" />
                  </svg>
                </NavigationMenu.Trigger>
                <NavigationMenu.Content className="absolute left-0 top-0 w-full">
                  <Container className="grid grid-cols-4 gap-8 py-8">
                    <div>
                      <p className="font-serif text-2xl">{node.name}</p>
                      {node.description && <p className="mt-2 text-sm text-muted">{node.description}</p>}
                      <NavigationMenu.Link asChild>
                        <Link
                          href={`/category/${node.slug}`}
                          className="mt-4 inline-block text-sm font-medium text-accent underline-offset-4 hover:underline"
                        >
                          Shop all {node.name}
                        </Link>
                      </NavigationMenu.Link>
                    </div>
                    {node.children.map((child) => (
                      <div key={child.id}>
                        <NavigationMenu.Link asChild>
                          <Link href={`/category/${child.slug}`} className="font-medium hover:text-accent">
                            {child.name}
                          </Link>
                        </NavigationMenu.Link>
                        {child.children.length > 0 && (
                          <ul className="mt-3 space-y-2">
                            {child.children.map((leaf) => (
                              <li key={leaf.id}>
                                <NavigationMenu.Link asChild>
                                  <Link href={`/category/${leaf.slug}`} className="text-sm text-muted hover:text-ink">
                                    {leaf.name}
                                  </Link>
                                </NavigationMenu.Link>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </Container>
                </NavigationMenu.Content>
              </NavigationMenu.Item>
            ),
          )}
        </NavigationMenu.List>
      </Container>
      <div className="absolute left-0 top-full w-full">
        <NavigationMenu.Viewport className="relative h-[var(--radix-navigation-menu-viewport-height)] w-full overflow-hidden border-b border-line bg-surface shadow-sm transition-[height] duration-200" />
      </div>
    </NavigationMenu.Root>
  );
}
