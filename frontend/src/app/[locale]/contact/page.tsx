import type { Metadata } from "next";
import { isLocale, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { alternates } from "@/lib/seo";
import { site } from "@/lib/site";
import { ContactForm } from "@/components/account/ContactForm";
import { Breadcrumbs, Container } from "@/components/ui/misc";

type Props = { params: Promise<{ locale: string }> };
const toLocale = (raw: string): Locale => (isLocale(raw) ? raw : "en");

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = toLocale((await params).locale);
  const t = getDictionary(locale);
  return {
    title: t.contact.title,
    description: t.contact.metaDescription,
    alternates: alternates(locale, "/contact"),
  };
}

export default async function ContactPage({ params }: Props) {
  const locale = toLocale((await params).locale);
  const t = getDictionary(locale);
  const etsy = site.social.find((s) => s.label === "Etsy");
  return (
    <Container className="py-12 sm:py-16">
      <Breadcrumbs items={[{ label: t.nav.home, href: localePath(locale, "/") }, { label: t.contact.title }]} />
      <div className="mt-6 grid gap-12 lg:grid-cols-[22rem_1fr]">
        <div>
          <h1 className="text-5xl sm:text-6xl">{t.contact.title}</h1>
          <p className="mt-5 text-lg text-muted">{t.contact.intro}</p>
          {etsy && (
            <p className="mt-6 text-sm text-muted">
              <a href={etsy.href} className="text-accent underline underline-offset-2" target="_blank" rel="noopener noreferrer">
                {t.contact.etsy}
              </a>
            </p>
          )}
        </div>
        <div className="rounded-[var(--radius-card)] border border-line bg-surface p-6 sm:p-8">
          <ContactForm />
        </div>
      </div>
    </Container>
  );
}
