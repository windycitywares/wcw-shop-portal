import { fmt, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { Container } from "@/components/ui/misc";
import { socialOf } from "@/lib/socialPlatforms";
import type { ShopConfig } from "@/lib/types";
import { cn } from "@/lib/utils";

type Account = NonNullable<ShopConfig["social"]>[number];

export function SocialGlyph({ platform, className }: { platform: string; className?: string }) {
  const p = socialOf(platform);
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={cn("size-5", className)}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      dangerouslySetInnerHTML={{ __html: p.glyph }}
    />
  );
}

/** A quiet row of icons: calm until hovered, when each shows its own network colour. 44px tap targets. */
export function SocialIcons({ accounts, locale, className }: { accounts: Account[]; locale: Locale; className?: string }) {
  if (accounts.length === 0) return null;
  const t = getDictionary(locale);
  return (
    <ul className={cn("flex items-center", className)} aria-label={t.footer.social}>
      {accounts.map((a) => {
        const p = socialOf(a.platform);
        if (a.url === "#") {
          // Not open yet: a plain icon with a tooltip, not a link that goes nowhere.
          return (
            <li key={a.id}>
              <span role="img" aria-label={`${p.label}: ${t.home.shopSoon}`} title={t.home.shopSoon} className="grid size-11 cursor-default place-items-center rounded-full opacity-60">
                <SocialGlyph platform={a.platform} />
              </span>
            </li>
          );
        }
        return (
          <li key={a.id}>
            <a
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={fmt(t.footer.followOn, { platform: p.label })}
              style={{ "--social-hover": p.hover } as React.CSSProperties}
              className="grid size-11 place-items-center rounded-full transition-colors hover:text-(--social-hover) focus-visible:text-(--social-hover)"
            >
              <SocialGlyph platform={a.platform} />
            </a>
          </li>
        );
      })}
    </ul>
  );
}

/** The Follow us row inside the dark footer, in the same tile pattern as the marketplaces: a badge in the network's own
 *  colour, the handle, and where it is. Five to a row on wide screens. A # address is shown greyed out as Coming soon. */
export function FollowBand({ accounts, locale }: { accounts: Account[]; locale: Locale }) {
  if (accounts.length === 0) return null;
  const t = getDictionary(locale);
  return (
    <section aria-labelledby="follow-heading" className="border-t border-white/10">
      <Container className="py-10">
        <h2 id="follow-heading" className="font-sans text-sm font-semibold text-white">
          {t.footer.followUs}
        </h2>
        <p className="mt-1 text-sm">{t.footer.followText}</p>
        <ul className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
          {accounts.map((a) => {
            const p = socialOf(a.platform);
            const soon = a.url === "#";
            const body = (
              <>
                <span aria-hidden="true" className="grid size-10 shrink-0 place-items-center rounded-full text-white ring-1 ring-white/30" style={{ background: p.hover }}>
                  <SocialGlyph platform={a.platform} className="size-5" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-white">{a.handle || p.label}</span>
                  <span className="block text-xs">{soon ? t.home.shopSoon : fmt(t.home.shopOn, { platform: p.label })}</span>
                </span>
              </>
            );
            const tile = "flex h-full items-center gap-3 rounded-[var(--radius-card)] border border-white/15 bg-white/5 p-3";
            return (
              <li key={a.id}>
                {soon ? (
                  <div className={cn(tile, "opacity-70")} style={{ borderLeft: `6px solid ${p.hover}` }}>
                    {body}
                  </div>
                ) : (
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={fmt(t.footer.followOn, { platform: p.label })}
                    className={cn(tile, "transition duration-200 hover:-translate-y-0.5 hover:bg-white/10 focus-visible:-translate-y-0.5 focus-visible:bg-white/10 motion-reduce:transition-none")}
                    style={{ borderLeft: `6px solid ${p.hover}` }}
                  >
                    {body}
                  </a>
                )}
              </li>
            );
          })}
        </ul>
      </Container>
    </section>
  );
}
