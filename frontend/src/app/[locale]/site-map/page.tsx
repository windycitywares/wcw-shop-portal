import type { Metadata } from "next";
import Link from "next/link";
import { HELP_NAV, HELP_TOPICS } from "@/content/help";
import { isLocale, localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getCategoryTree } from "@/lib/api";
import { alternates } from "@/lib/seo";
import type { CategoryNode } from "@/lib/types";
import { Breadcrumbs, Container } from "@/components/ui/misc";

export const revalidate = 3600;

type Props = { params: Promise<{ locale: string }> };

const TEXT: Record<Locale, { title: string; description: string; shop: string; all: string; deals: string; help: string; more: string }> = {
  en: { title: "Site map", description: "Every section of the shop in one place.", shop: "Shop", all: "All products", deals: "Deals", help: "Help", more: "More" },
  es: { title: "Mapa del sitio", description: "Todas las secciones de la tienda en un solo lugar.", shop: "Tienda", all: "Todos los productos", deals: "Ofertas", help: "Ayuda", more: "Más" },
  nl: { title: "Sitemap", description: "Alle onderdelen van de winkel op één plek.", shop: "Winkel", all: "Alle producten", deals: "Aanbiedingen", help: "Hulp", more: "Meer" },
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const lang: Locale = isLocale(locale) ? locale : "en";
  return { title: TEXT[lang].title, description: TEXT[lang].description, alternates: alternates(lang, "/site-map") };
}

function Tree({ nodes, lang }: { nodes: CategoryNode[]; lang: Locale }) {
  return (
    <ul className="mt-2 space-y-1.5">
      {nodes.map((n) => (
        <li key={n.slug}>
          <Link href={localePath(lang, `/category/${n.slug}`)} className="hover:underline">
            {n.name}
          </Link>
          {n.children.length > 0 && (
            <div className="ml-4">
              <Tree nodes={n.children} lang={lang} />
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

/** A human-readable site map; the search-engine one is /sitemap.xml. */
export default async function SiteMapPage({ params }: Props) {
  const { locale } = await params;
  const lang: Locale = isLocale(locale) ? locale : "en";
  const tx = TEXT[lang];
  const t = getDictionary(lang);
  const tree = await getCategoryTree();
  return (
    <Container className="py-12 sm:py-16">
      <Breadcrumbs items={[{ label: t.nav.home, href: localePath(lang, "/") }, { label: tx.title }]} />
      <h1 className="mt-8 font-serif text-4xl font-light text-ink">{tx.title}</h1>
      <p className="mt-2 text-muted">{tx.description}</p>
      <div className="mt-10 grid gap-10 md:grid-cols-3">
        <section aria-labelledby="sm-shop">
          <h2 id="sm-shop" className="font-sans text-sm font-semibold text-ink">{tx.shop}</h2>
          <ul className="mt-2 space-y-1.5">
            <li><Link href={localePath(lang, "/shop")} className="hover:underline">{tx.all}</Link></li>
            <li><Link href={localePath(lang, "/deals")} className="hover:underline">{tx.deals}</Link></li>
          </ul>
          <Tree nodes={tree} lang={lang} />
        </section>
        <section aria-labelledby="sm-help">
          <h2 id="sm-help" className="font-sans text-sm font-semibold text-ink">{tx.help}</h2>
          <ul className="mt-2 space-y-1.5">
            {HELP_TOPICS.map((k) => (
              <li key={k}><Link href={localePath(lang, `/help/${k}`)} className="hover:underline">{HELP_NAV[lang][k]}</Link></li>
            ))}
          </ul>
        </section>
        <section aria-labelledby="sm-more">
          <h2 id="sm-more" className="font-sans text-sm font-semibold text-ink">{tx.more}</h2>
          <ul className="mt-2 space-y-1.5">
            <li><Link href={localePath(lang, "/track-order")} className="hover:underline">{t.footer.findOrder}</Link></li>
            <li><Link href={localePath(lang, "/contact")} className="hover:underline">{t.footer.contact}</Link></li>
            <li><Link href={localePath(lang, "/login")} className="hover:underline">{t.nav.signIn}</Link></li>
          </ul>
        </section>
      </div>
    </Container>
  );
}
