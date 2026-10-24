import { fmt, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
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

/** "Follow us" pills with the handle, so visitors know what to search for. */
export function FollowPills({ accounts, locale, onDark = false }: { accounts: Account[]; locale: Locale; onDark?: boolean }) {
  if (accounts.length === 0) return null;
  const t = getDictionary(locale);
  return (
    <ul className="flex flex-wrap gap-3" aria-label={t.footer.followUs}>
      {accounts.map((a) => {
        const p = socialOf(a.platform);
        if (a.url === "#") {
          return (
            <li key={a.id}>
              <span
                title={t.home.shopSoon}
                className={cn("inline-flex min-h-11 cursor-default items-center gap-2 rounded-full border px-4 text-sm font-medium opacity-60", onDark ? "border-white/25 text-white" : "border-line bg-surface text-ink")}
              >
                <SocialGlyph platform={a.platform} className="size-[1.125rem]" />
                {a.handle || p.label}
                <span className="text-xs font-normal">· {t.home.shopSoon}</span>
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
              className={cn("inline-flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors hover:border-(--social-hover) hover:text-(--social-hover) focus-visible:border-(--social-hover)", onDark ? "border-white/25 text-white hover:bg-white" : "border-line bg-surface text-ink")}
            >
              <SocialGlyph platform={a.platform} className="size-[1.125rem]" />
              {a.handle || p.label}
            </a>
          </li>
        );
      })}
    </ul>
  );
}
