import Link from "next/link";
import { fmt, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { site } from "@/lib/site";
import { Container } from "@/components/ui/misc";
import { Logo } from "@/components/ui/Logo";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { NewsletterForm } from "./NewsletterForm";

export function Footer({ locale }: { locale: Locale }) {
  const t = getDictionary(locale);
  const l = (p: string) => localePath(locale, p);
  const year = new Date().getFullYear();
  const columns = [
    {
      title: t.footer.shop,
      links: [
        { label: t.nav.shopAll, href: l("/shop") },
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
      links: [{ label: t.footer.contact, href: l("/contact") }],
    },
  ];
  return (
    <footer className="mt-28 bg-night text-night-muted [&_*:focus-visible]:outline-white">
      <Container className="grid gap-12 py-16 md:grid-cols-[1.6fr_1fr_1fr_1fr]">
        <div className="max-w-sm">
          <Logo tone="reverse" title="WindyCityWares" className="mb-8 h-10 w-auto" />
          <p className="font-serif text-3xl font-light text-white">{t.footer.newsletterTitle}</p>
          <p className="mt-3 text-sm">{t.footer.newsletterText}</p>
          <NewsletterForm />
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
        <p>{fmt(t.footer.rights, { year })}</p>
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <LanguageSwitcher variant="inline" />
          <ul className="flex gap-4" aria-label={t.footer.social}>
            {site.social.map((s) => (
              <li key={s.href}>
                <a href={s.href} target="_blank" rel="noopener noreferrer" className="hover:text-white">
                  {s.label}
                  <span className="sr-only"> {t.footer.newTab}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </Container>
    </footer>
  );
}
