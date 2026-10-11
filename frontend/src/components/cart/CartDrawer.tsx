"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/utils";
import { ButtonLink } from "@/components/ui/Button";
import { CartLines } from "./CartLines";

export function CartDrawer() {
  const { isOpen, setOpen, lines, subtotal } = useCart();
  const close = () => setOpen(false);
  return (
    <Dialog.Root open={isOpen} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/40" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-canvas shadow-xl">
          <div className="flex items-center justify-between border-b border-line px-6 py-4">
            <Dialog.Title className="font-serif text-2xl">Your cart</Dialog.Title>
            <Dialog.Close className="grid size-10 place-items-center rounded-full hover:bg-sand">
              <span aria-hidden="true" className="text-2xl leading-none">
                ×
              </span>
              <span className="sr-only">Close cart</span>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Items in your shopping cart</Dialog.Description>
          <div className="flex-1 overflow-y-auto px-6">
            {lines.length === 0 ? (
              <p className="py-16 text-center text-muted">Your cart is empty.</p>
            ) : (
              <CartLines onNavigate={close} />
            )}
          </div>
          {lines.length > 0 && (
            <div className="space-y-4 border-t border-line px-6 py-5">
              <div className="flex justify-between text-base">
                <span>Subtotal</span>
                <span className="font-medium">{formatPrice(subtotal)}</span>
              </div>
              <p className="text-xs text-muted">Shipping and taxes are calculated at checkout.</p>
              <ButtonLink href="/cart" onClick={close} className="w-full" size="lg">
                View cart
              </ButtonLink>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
