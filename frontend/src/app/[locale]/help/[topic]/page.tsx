import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HELP, HELP_NAV, HELP_TOPICS, type HelpTopic } from "@/content/help";
import { isLocale, localePath, locales, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getShopConfig } from "@/lib/api";
import { alternates } from "@/lib/seo";
import { cn, formatPrice } from "@/lib/utils";
import { JsonLd } from "@/components/seo/JsonLd";
import { Breadcrumbs, Container } from "@/components/ui/misc";

export const revalidate = 300;

type Props = { params: Promise<{ locale: string; topic: string }> };

export function generateStaticParams() {
  return locales.flatMap((locale) => HELP_TOPICS.map((topic) => ({ locale, topic })));
}

function resolve(locale: string, topic: string) {
  const lang: Locale = isLocale(locale) ? locale : "en";
  if (!(HELP_TOPICS as readonly string[]).includes(topic)) return null;
  return { lang, topic: topic as HelpTopic, page: HELP[lang][topic as HelpTopic] };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, topic } = await params;
  const found = resolve(locale, topic);
  if (!found) return {};
  return { title: found.page.title, description: found.page.description, alternates: alternates(found.lang, `/help/${topic}`) };
}

export default async function HelpPage({ params }: Props) {
  const { locale, topic } = await params;
  const found = resolve(locale, topic);
  if (!found) notFound();
  const { lang, page } = found;
  const t = getDictionary(lang);
  const config = await getShopConfig(lang);

  // Live numbers from Admin → Settings → Shipping, so the policy never disagrees with the cart.
  const days = config?.delivery_days ?? [4, 10];
  const vars: Record<string, string> = {
    flat: formatPrice(config?.flat_shipping_rate ?? 8.95, "USD", lang),
    free: config?.free_shipping_threshold != null ? formatPrice(config.free_shipping_threshold, "USD", lang) : "—",
    handling: `${config?.handling_days?.[0] ?? 1}–${config?.handling_days?.[1] ?? 3}`,
    transit: `${config?.transit_days?.[0] ?? 3}–${config?.transit_days?.[1] ?? 7}`,
    total: `${days[0]}–${days[1]}`,
  };
  const fill = (text: string) => text.replace(/\{(\w+)\}/g, (m, k) => vars[k] ?? m);

  return (
    <Container className="py-12 sm:py-16">
      <Breadcrumbs items={[{ label: t.nav.home, href: localePath(lang, "/") }, { label: page.title }]} />
      <div className="mt-8 grid gap-12 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label={t.footer.help} className="text-sm">
          <ul className="space-y-1 lg:sticky lg:top-24">
            {HELP_TOPICS.map((key) => (
              <li key={key}>
                <Link
                  href={localePath(lang, `/help/${key}`)}
                  aria-current={key === topic ? "page" : undefined}
                  className={cn("block rounded-md px-3 py-2 hover:bg-sand", key === topic && "bg-sand font-medium")}
                >
                  {HELP_NAV[lang][key]}
                </Link>
              </li>
            ))}
            <li>
              <Link href={localePath(lang, "/contact")} className="block rounded-md px-3 py-2 hover:bg-sand">
                {t.footer.contact}
              </Link>
            </li>
          </ul>
        </nav>
        <article className="max-w-[68ch]">
          <h1 className="text-5xl">{page.title}</h1>
          <p className="mt-4 text-lg text-muted">{page.description}</p>
          {page.sections.map((s) => (
            <section key={s.heading} className="mt-10">
              <h2 className="text-2xl">{s.heading}</h2>
              {s.paragraphs?.map((p) => (
                <p key={p} className="mt-3 leading-relaxed text-muted">
                  {fill(p)}
                </p>
              ))}
              {s.bullets && (
                <ul className="mt-3 list-disc space-y-1.5 pl-5 leading-relaxed text-muted">
                  {s.bullets.map((b) => (
                    <li key={b}>{fill(b)}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </article>
      </div>
      {topic === "faq" && (
        <JsonLd
          data={{
            "@context": "https://schema.org",
            "@type": "FAQPage",
            mainEntity: page.sections.map((s) => ({
              "@type": "Question",
              name: s.heading,
              acceptedAnswer: { "@type": "Answer", text: fill((s.paragraphs ?? s.bullets ?? []).join(" ")) },
            })),
          }}
        />
      )}
    </Container>
  );
}
