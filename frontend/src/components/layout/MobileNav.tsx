"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { useState } from "react";
import { useI18n } from "@/i18n/client";
import type { CategoryNode } from "@/lib/types";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { ThemeSwitcher } from "./ThemeSwitcher";

function Branch({ node, onNavigate }: { node: CategoryNode; onNavigate: () => void }) {
  const { t, href, fmt } = useI18n();
  if (node.children.length === 0) {
    return (
      <Link href={href(`/category/${node.slug}`)} onClick={onNavigate} className="block py-3">
        {node.name}
      </Link>
    );
  }
  return (
    <details className="group" open>
      <summary className="flex cursor-pointer list-none items-center justify-between py-3 font-serif text-xl [&::-webkit-details-marker]:hidden">
        {node.name}
        <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-45">
          +
        </span>
      </summary>
      <ul className="mb-3 border-l border-line pl-4">
        <li>
          <Link href={href(`/category/${node.slug}`)} onClick={onNavigate} className="block py-2 text-sm text-accent">
            {fmt(t.nav.allIn, { name: node.name })}
          </Link>
        </li>
        {node.children.map((child) => (
          <li key={child.id} className="text-[0.9375rem]">
            <Branch node={child} onNavigate={onNavigate} />
          </li>
        ))}
      </ul>
    </details>
  );
}

export function MobileNav({ tree }: { tree: CategoryNode[] }) {
  const [open, setOpen] = useState(false);
  const { t, href } = useI18n();
  const close = () => setOpen(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger className="-ml-2 grid size-10 place-items-center rounded-full hover:bg-sand lg:hidden" title={t.nav.openMenu}>
        <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
        </svg>
        <span className="sr-only">{t.nav.openMenu}</span>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-night/50" />
        <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[88vw] max-w-sm flex-col bg-canvas shadow-xl">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <Dialog.Title className="font-serif text-xl">{t.nav.menu}</Dialog.Title>
            <Dialog.Close className="grid size-10 place-items-center rounded-full hover:bg-sand" title={t.nav.closeMenu}>
              <span aria-hidden="true" className="text-2xl leading-none">
                ×
              </span>
              <span className="sr-only">{t.nav.closeMenu}</span>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">{t.nav.browseCategories}</Dialog.Description>
          <nav aria-label={t.nav.categories} className="flex-1 overflow-y-auto px-5 py-3">
            <ul className="divide-y divide-line">
              <li>
                <Link href={href("/shop")} onClick={close} className="block py-3 font-medium">
                  {t.nav.shopAll}
                </Link>
              </li>
              <li>
                <Link href={href("/deals")} onClick={close} className="block py-3 font-medium">
                  {t.nav.deals}
                </Link>
              </li>
              {tree.map((node) => (
                <li key={node.id}>
                  <Branch node={node} onNavigate={close} />
                </li>
              ))}
            </ul>
          </nav>
          <div className="border-t border-line px-5 py-4">
            <p className="mb-2 text-sm text-muted">{t.nav.language}</p>
            <LanguageSwitcher variant="inline" className="[&_a]:text-ink [&_a[aria-current]]:font-semibold" />
            <p className="mb-2 mt-5 text-sm text-muted">{t.theme.label}</p>
            <ThemeSwitcher variant="inline" />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
