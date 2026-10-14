import type { Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getShopConfig } from "@/lib/api";

/** One line from Admin → Settings → General ("Free engraving this week"). Renders nothing when switched off. */
export async function AnnouncementBar({ locale }: { locale: Locale }) {
  const config = await getShopConfig(locale);
  if (!config?.announcement) return null;
  const t = getDictionary(locale);
  return (
    <aside aria-label={t.nav.announcement} className="bg-ink px-4 py-2 text-center text-sm text-canvas">
      {config.announcement}
    </aside>
  );
}
