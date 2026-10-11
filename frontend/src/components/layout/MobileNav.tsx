"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { useState } from "react";
import type { CategoryNode } from "@/lib/types";

function Branch({ node, onNavigate }: { node: CategoryNode; onNavigate: () => void }) {
  if (node.children.length === 0) {
    return (
      <Link href={`/category/${node.slug}`} onClick={onNavigate} className="block py-2.5">
        {node.name}
      </Link>
    );
  }
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between py-2.5">
        {node.name}
        <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-45">
          +
        </span>
      </summary>
      <ul className="mb-2 ml-3 border-l border-line pl-4">
        <li>
          <Link href={`/category/${node.slug}`} onClick={onNavigate} className="block py-2 text-sm text-accent">
            All {node.name}
          </Link>
        </li>
        {node.children.map((child) => (
          <li key={child.id} className="text-sm">
            <Branch node={child} onNavigate={onNavigate} />
          </li>
        ))}
      </ul>
    </details>
  );
}

export function MobileNav({ tree }: { tree: CategoryNode[] }) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger className="grid size-10 place-items-center rounded-full hover:bg-sand md:hidden">
        <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
        </svg>
        <span className="sr-only">Open menu</span>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/40" />
        <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[85vw] max-w-sm flex-col bg-canvas shadow-xl">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <Dialog.Title className="font-serif text-xl">Menu</Dialog.Title>
            <Dialog.Close className="grid size-10 place-items-center rounded-full hover:bg-sand">
              <span aria-hidden="true" className="text-2xl leading-none">
                ×
              </span>
              <span className="sr-only">Close menu</span>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Browse shop categories</Dialog.Description>
          <nav aria-label="Shop categories" className="flex-1 overflow-y-auto px-5 py-3">
            <ul className="divide-y divide-line">
              <li>
                <Link href="/shop" onClick={close} className="block py-2.5 font-medium">
                  Shop all
                </Link>
              </li>
              {tree.map((node) => (
                <li key={node.id}>
                  <Branch node={node} onNavigate={close} />
                </li>
              ))}
            </ul>
          </nav>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
