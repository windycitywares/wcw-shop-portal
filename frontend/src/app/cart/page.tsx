"use client";

import Link from "next/link";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/utils";
import { CartLines } from "@/components/cart/CartLines";
import { Button } from "@/components/ui/Button";
import { Container, EmptyState } from "@/components/ui/misc";

export default function CartPage() {
  const { lines, subtotal } = useCart();
  return (
    <Container className="py-12">
      <h1 className="text-4xl sm:text-5xl">Your cart</h1>
      {lines.length === 0 ? (
        <div className="mt-10">
          <EmptyState title="Your cart is empty">
            <Link href="/shop" className="underline">
              Continue shopping
            </Link>
          </EmptyState>
        </div>
      ) : (
        <div className="mt-10 grid gap-12 lg:grid-cols-[1fr_22rem]">
          <section aria-label="Cart items">
            <CartLines />
          </section>
          <aside aria-label="Order summary" className="h-fit rounded-[var(--radius-card)] border border-line bg-surface p-6">
            <h2 className="text-2xl">Summary</h2>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt>Subtotal</dt>
                <dd className="font-medium">{formatPrice(subtotal)}</dd>
              </div>
              <div className="flex justify-between text-muted">
                <dt>Shipping & tax</dt>
                <dd>At checkout</dd>
              </div>
            </dl>
            {/* Checkout (address -> shipping -> payment review) is the next build step. */}
            <Button size="lg" className="mt-6 w-full" disabled aria-describedby="checkout-note">
              Checkout
            </Button>
            <p id="checkout-note" className="mt-3 text-xs text-muted">
              Online checkout is coming soon.
            </p>
          </aside>
        </div>
      )}
    </Container>
  );
}
