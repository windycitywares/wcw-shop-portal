import type { Metadata, Viewport } from "next";
import { notFound } from "next/navigation";
import { Providers } from "@/components/Providers";
import { CartDrawer } from "@/components/cart/CartDrawer";
import { Footer } from "@/components/layout/Footer";
import { Header } from "@/components/layout/Header";
import { JsonLd, organizationLd } from "@/components/seo/JsonLd";
import { I18nProvider } from "@/i18n/client";
import { isLocale, locales, ogLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { site } from "@/lib/site";
import { body, display } from "../fonts";
import "../globals.css";

type Props = { children: React.ReactNode; params: Promise<{ locale: string }> };

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = getDictionary(locale);
  return {
    metadataBase: new URL(site.url),
    title: { default: t.meta.title, template: `%s | ${site.name}` },
    description: t.meta.description,
    applicationName: site.name,
    openGraph: { type: "website", siteName: site.name, locale: ogLocale[locale], url: site.url },
    twitter: { card: "summary_large_image" },
    // Pre-launch builds also send noindex on every page (robots.txt alone doesn't remove pages from Google).
    ...(site.allowIndexing ? {} : { robots: { index: false, follow: false } }),
  };
}

export const viewport: Viewport = {
  themeColor: "#f2f3ef",
  width: "device-width",
  initialScale: 1,
};

/**
 * Storefront template, one per language: <Header /> + <main> + <Footer />.
 * To re-theme the store, edit the tokens in globals.css and the fonts in app/fonts.ts.
 */
export default async function LocaleLayout({ children, params }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  return (
    <html lang={locale} className={`${display.variable} ${body.variable}`}>
      <body className="flex min-h-dvh flex-col font-sans antialiased">
        <a href="#main" className="skip-link">
          {t.nav.skip}
        </a>
        <I18nProvider locale={locale}>
          <Providers>
            <Header locale={locale} />
            <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">
              {children}
            </main>
            <Footer locale={locale} />
            <CartDrawer />
          </Providers>
        </I18nProvider>
        <JsonLd data={organizationLd()} />
      </body>
    </html>
  );
}
