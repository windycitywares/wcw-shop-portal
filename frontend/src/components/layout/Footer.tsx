import Link from "next/link";
import { ConsentSettingsLink } from "@/components/analytics/Analytics";
import { HELP_NAV } from "@/content/help";
import { fmt, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getShopConfig } from "@/lib/api";
import { FollowPills } from "@/components/ui/SocialLinks";
import { MarketplaceBand } from "@/components/catalog/ShopLinkTiles";
import { Container } from "@/components/ui/misc";
import { Logo } from "@/components/ui/Logo";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { NewsletterForm } from "./NewsletterForm";

export async function Footer({ locale }: { locale: Locale }) {
  const t = getDictionary(locale);
  const config = await getShopConfig(locale);
  const shops = config?.shop_links ?? [];
  const social = config?.social ?? [];
  const l = (p: string) => localePath(locale, p);
  const year = new Date().getFullYear();
  const columns = [
    {
      title: t.footer.shop,
      links: [
        { label: t.nav.shopAll, href: l("/shop") },
        { label: t.nav.deals, href: l("/deals") },
        { label: t.footer.newArrivals, href: l("/shop?sort=newest") },
        { label: t.nav.search, href: l("/search") },
      ],
    },
    {
      title: t.footer.yourAccount,
      links: [
        { label: t.nav.signIn, href: l("/login") },
        { label: t.nav.account, href: l("/account") },
        { label: t.footer.cart, href: l("/cart") },
      ],
    },
    {
      title: t.footer.help,
      links: [
        { label: t.footer.findOrder, href: l("/track-order") },
        { label: HELP_NAV[locale].guide, href: l("/help/guide") },
        { label: HELP_NAV[locale].faq, href: l("/help/faq") },
        { label: HELP_NAV[locale].shipping, href: l("/help/shipping") },
        { label: HELP_NAV[locale].returns, href: l("/help/returns") },
        { label: HELP_NAV[locale].privacy, href: l("/help/privacy") },
        { label: HELP_NAV[locale].terms, href: l("/help/terms") },
        { label: t.footer.contact, href: l("/contact") },
        { label: ({ en: "Site map", es: "Mapa del sitio", nl: "Sitemap" } as Record<string, string>)[locale] ?? "Site map", href: l("/site-map") },
      ],
    },
  ];
  return (
    <>
    <MarketplaceBand links={shops} locale={locale} />
    <footer className={`${shops.length > 0 ? "" : "mt-28"} bg-night text-night-muted [&_*:focus-visible]:outline-white`}>
      <Container className="grid gap-12 py-16 md:grid-cols-[1.6fr_1fr_1fr_1fr]">
        <div className="max-w-sm">
          <Logo tone="reverse" title="WindyCityWares" className="mb-8 h-10 w-auto" />
          <p className="font-serif text-3xl font-light text-white">{t.footer.newsletterTitle}</p>
          <p className="mt-3 text-sm">{t.footer.newsletterText}</p>
          <NewsletterForm />
          {social.length > 0 && (
            <div className="mt-8">
              <p className="mb-3 text-sm font-semibold text-white">{t.footer.followUs}</p>
              <FollowPills accounts={social} locale={locale} onDark />
            </div>
          )}
        </div>
        {columns.map((col) => (
          <nav key={col.title} aria-label={col.title}>
            <h2 className="font-sans text-sm font-semibold text-white">{col.title}</h2>
            <ul className="mt-4 space-y-2.5 text-sm">
              {col.links.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="hover:text-white">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </Container>
      <Container className="flex flex-col gap-5 border-t border-white/10 py-7 text-sm sm:flex-row sm:items-center sm:justify-between">
        <p>
          {fmt(t.footer.rights, { year })}{" "}
          <ConsentSettingsLink className="ml-3 underline hover:text-white" />
        </p>
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <LanguageSwitcher variant="inline" />
        </div>
      </Container>
    </footer>
    </>
  );
}
