"use client";

import { useOptionalI18n } from "@/i18n/client";
import { Container } from "@/components/ui/misc";

/**
 * Placeholders shown by the storefront's loading.tsx files while a server-rendered page fetches its data, shaped like
 * the page that will replace them so nothing jumps. Screen readers hear "Loading…" once; the shapes are hidden from them.
 */
function Busy({ children }: { children: React.ReactNode }) {
  const { t } = useOptionalI18n();
  return (
    <div role="status" aria-busy="true">
      <span className="sr-only">{t.account.loading}</span>
      <div aria-hidden="true">{children}</div>
    </div>
  );
}

function CardSkeleton() {
  return (
    <div>
      <div className="skeleton aspect-[4/5] w-full" />
      <div className="skeleton mt-4 h-4 w-3/4" />
      <div className="skeleton mt-2 h-4 w-1/3" />
    </div>
  );
}

/** Shop, category, search and deals: a title, the filter column and a grid of cards. */
export function ListingSkeleton() {
  return (
    <Busy>
      <Container className="py-10 sm:py-14">
        <div className="skeleton h-10 w-64 max-w-full" />
        <div className="skeleton mt-4 h-4 w-96 max-w-full" />
        <div className="mt-10 grid gap-10 border-t border-line pt-8 lg:grid-cols-[15rem_1fr] lg:gap-14">
          <div className="hidden space-y-4 lg:block">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="skeleton h-5 w-full" />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-12 sm:gap-x-6 md:grid-cols-3 lg:gap-x-8">
            {Array.from({ length: 6 }, (_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        </div>
      </Container>
    </Busy>
  );
}

/** A product page: breadcrumbs, the photo and the buying panel. */
export function ProductSkeleton() {
  return (
    <Busy>
      <Container className="py-8 sm:py-12">
        <div className="skeleton h-4 w-56 max-w-full" />
        <div className="mt-8 grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-16 xl:gap-24">
          <div className="skeleton aspect-[4/5] w-full" />
          <div>
            <div className="skeleton h-4 w-32" />
            <div className="skeleton mt-4 h-10 w-4/5" />
            <div className="skeleton mt-6 h-7 w-28" />
            <div className="mt-8 space-y-3">
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-11/12" />
              <div className="skeleton h-4 w-2/3" />
            </div>
            <div className="skeleton mt-10 h-12 w-full" />
          </div>
        </div>
      </Container>
    </Busy>
  );
}
