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

/** The Follow us section shown above the footer on every page, in the same tile pattern as the marketplaces: a badge in the
 *  network's own colour, the handle, and where it is. A # address is shown greyed out as Coming soon. */
export function FollowBand({ accounts, locale, stacked = false }: { accounts: Account[]; locale: Locale; stacked?: boolean }) {
  if (accounts.length === 0) return null;
  const t = getDictionary(locale);
  return (
    <section aria-labelledby="follow-heading" className={cn("border-t border-line bg-canvas py-12", !stacked && "mt-20")}>
      <Container>
        <h2 id="follow-heading" className="font-serif text-3xl">
          {t.footer.followUs}
        </h2>
        <p className="mt-2 text-muted">{t.footer.followText}</p>
        <ul className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {accounts.map((a) => {
            const p = socialOf(a.platform);
            const soon = a.url === "#";
            const body = (
              <>
                <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-full text-white" style={{ background: p.hover }}>
                  <SocialGlyph platform={a.platform} className="size-6" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-semibold text-ink">{a.handle || p.label}</span>
                  <span className="block text-sm text-muted">{soon ? t.home.shopSoon : fmt(t.home.shopOn, { platform: p.label })}</span>
                </span>
                {!soon && (
                  <span aria-hidden="true" className="ml-auto hidden shrink-0 rounded-full px-3 py-1 text-xs font-semibold text-white xl:block" style={{ background: p.hover }}>
                    {t.footer.followCta}
                  </span>
                )}
              </>
            );
            return (
              <li key={a.id}>
                {soon ? (
                  <div
                    className="flex h-full items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-3 opacity-80"
                    style={{ borderLeft: `6px solid ${p.hover}` }}
                  >
                    {body}
                  </div>
                ) : (
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={fmt(t.footer.followOn, { platform: p.label })}
                    className="flex h-full items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-3 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-lg focus-visible:-translate-y-0.5 focus-visible:shadow-lg motion-reduce:transition-none"
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
