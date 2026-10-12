"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/utils";
import { ButtonLink } from "@/components/ui/Button";
import { CartLines } from "./CartLines";

export function CartDrawer() {
  const { isOpen, setOpen, lines, subtotal } = useCart();
  const { t, href, locale } = useI18n();
  const close = () => setOpen(false);
  return (
    <Dialog.Root open={isOpen} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-night/50" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-canvas shadow-xl">
          <div className="flex items-center justify-between border-b border-line px-6 py-4">
            <Dialog.Title className="font-serif text-2xl font-light">{t.cart.title}</Dialog.Title>
            <Dialog.Close className="grid size-10 place-items-center rounded-full hover:bg-sand">
              <span aria-hidden="true" className="text-2xl leading-none">
                ×
              </span>
              <span className="sr-only">{t.cart.close}</span>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">{t.cart.description}</Dialog.Description>
          <div className="flex-1 overflow-y-auto px-6">
            {lines.length === 0 ? (
              <p className="py-16 text-center text-muted">{t.cart.empty}</p>
            ) : (
              <CartLines onNavigate={close} />
            )}
          </div>
          {lines.length > 0 && (
            <div className="space-y-4 border-t border-line bg-surface px-6 py-5">
              <div className="flex justify-between text-base">
                <span>{t.cart.subtotal}</span>
                <span className="font-medium">{formatPrice(subtotal, "USD", locale)}</span>
              </div>
              <p className="text-xs text-muted">{t.cart.shippingNote}</p>
              <ButtonLink href={href("/cart")} onClick={close} className="w-full" size="lg">
                {t.cart.view}
              </ButtonLink>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
