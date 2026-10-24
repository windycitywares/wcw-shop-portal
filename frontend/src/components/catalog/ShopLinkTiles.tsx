import { fmt, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { platformOf } from "@/lib/shopPlatforms";
import type { ShopConfig } from "@/lib/types";

type Item = NonNullable<ShopConfig["shop_links"]>[number];

/** The owner's other shops as colour-coded tiles. The colour and the "on Etsy" line say which marketplace it is at a glance;
 *  hovering or focusing a tile shows the owner's blurb, and a click opens the shop in a new tab. */
export function ShopLinkTiles({ links, locale }: { links: Item[]; locale: Locale }) {
  const t = getDictionary(locale);
  return (
    <ul className="flex flex-wrap gap-4">
      {links.map((l) => {
        const p = platformOf(l.platform);
        const tipId = `shop-tip-${l.id}`;
        return (
          <li key={l.id} className="group relative">
            <a
              href={l.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-describedby={l.blurb ? tipId : undefined}
              className="flex min-w-60 items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-3 pr-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-lg focus-visible:-translate-y-0.5 focus-visible:shadow-lg motion-reduce:transition-none"
              style={{ borderLeft: `6px solid ${p.bg}` }}
            >
              <span
                aria-hidden="true"
                className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-full text-xl font-bold"
                style={{ background: p.bg, color: p.fg }}
              >
                {l.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={l.image_url} alt="" className="size-full object-cover" loading="lazy" referrerPolicy="no-referrer" />
                ) : (
                  (p.id === "other" ? l.name : p.label).charAt(0).toUpperCase()
                )}
              </span>
              <span className="min-w-0">
                <span className="block truncate font-semibold text-ink">{l.name}</span>
                <span className="block text-sm text-muted">{p.id === "other" ? t.home.shopOpens : fmt(t.home.shopOn, { platform: p.label })}</span>
                {l.blurb && <span className="mt-1 line-clamp-2 block text-xs text-muted md:hidden">{l.blurb}</span>}
              </span>
              <svg aria-hidden="true" viewBox="0 0 24 24" className="ml-auto size-4 shrink-0 text-muted" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M7 17L17 7M8 7h9v9" />
              </svg>
              <span className="sr-only"> {t.footer.newTab}</span>
            </a>
            {l.blurb && (
              <span
                id={tipId}
                role="tooltip"
                className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 hidden w-64 -translate-x-1/2 rounded-[var(--radius-card)] bg-night p-3 text-sm text-white opacity-0 shadow-xl transition-opacity duration-150 md:block md:group-focus-within:opacity-100 md:group-hover:opacity-100"
              >
                <strong className="block">{l.name}</strong>
                <span className="mt-1 block text-night-muted">{l.blurb}</span>
                <span className="mt-2 block text-xs text-night-muted">{t.home.shopOpens}</span>
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
