import type { Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getShopConfig } from "@/lib/api";
import { SocialIcons } from "@/components/ui/SocialLinks";
import { Container } from "@/components/ui/misc";

/** The strip above the header: the line from Admin → Settings → General ("Free engraving this week") and the social icons
 *  from Settings → Social media. Renders nothing when both are off. */
export async function AnnouncementBar({ locale }: { locale: Locale }) {
  const config = await getShopConfig(locale);
  const social = config?.social ?? [];
  if (!config?.announcement && social.length === 0) return null;
  const t = getDictionary(locale);
  return (
    <aside aria-label={t.nav.announcement} className="bg-ink text-canvas">
      <Container className="flex min-h-9 items-center justify-between gap-4 text-sm">
        <p className="flex-1 py-2 text-center sm:text-left">{config?.announcement}</p>
        <SocialIcons accounts={social} locale={locale} className="-my-1 shrink-0 [&_a]:size-9" />
      </Container>
    </aside>
  );
}
